"""The review tools with real renders: observe, judge and the checks, and what a reviewer may deliver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import (
    Sandbox,
)
from support.flow import SEEN_RED, needs_craft, production_spec, runner, use
from support.rules import RULES
from support.scripted import turn
from support.settings import settings


def test_observe_needs_a_render_really_viewed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    ledger = Ledger(config.layout.ledger)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    box = Toolbox(context)
    seen = "Quadrato rosso pieno, bordi netti, nessun difetto visibile nel render."
    arguments = {"file": "a.png", "seen": seen}
    assert box.call("a", "observe", arguments)["is_error"]
    proof = json.loads(box.call("b", "render", {"path": "a.png"})["content"])["proofs"][0]
    assert box.call("c", "observe", arguments)["is_error"]
    box.call("d", "view_image", {"path": proof})
    assert not box.call("e", "observe", arguments).get("is_error")


def critic_box(tmp_path: Path) -> tuple[Toolbox, Path]:
    """A critic on a real ticket, with its own work folder."""
    work = tmp_path / "work"
    work.mkdir()
    ledger = Ledger(settings(tmp_path).layout.ledger)
    ticket = ledger.open(production_spec(), "p")
    artifacts = FileStore(tmp_path / "artifacts")
    context = ToolContext(
        "critic", "p", ticket, "i", ledger, Sandbox(work), CommandIndex([]), artifacts, rules=RULES
    )
    return Toolbox(context), work


LOOKED = "Quadrato rosso pieno, bordi netti, nessun difetto visibile nel render della pagina."


REASONED = "Rispetto alla versione precedente il segno regge meglio a piccola scala e resta riconoscibile."


@pytest.mark.parametrize(
    ("tool", "arguments", "refusal"),
    [
        (
            "observe",
            {"file": "a.png", "seen": LOOKED, "check": "critique"},
            "non è un controllo di osservazione",
        ),
        (
            "judge",
            {
                "file": "a.png",
                "compare": ["b.png"],
                "why": REASONED,
                "check": "visual_review",
                "result": "PASS",
            },
            "non è un giudizio",
        ),
        ("record_requirement", {"check": "visual_review"}, "ha il suo strumento"),
        ("record_requirement", {"check": "critique"}, "ha il suo strumento"),
        ("record_requirement", {"check": "diversity"}, "ha il suo strumento"),
    ],
    ids=[
        "observe-judgement",
        "judge-observation",
        "requirement-observation",
        "requirement-judgement",
        "requirement-measure",
    ],
)
def test_each_kind_of_check_is_recorded_by_its_own_tool(
    tmp_path: Path, tool: str, arguments: dict, refusal: str
) -> None:
    """The kind of a check (registry/checks.json) decides which tool records it: the others refuse it."""
    box, _ = critic_box(tmp_path)
    if tool == "record_requirement":
        arguments = {"file": "a.png", "result": "PASS", "note": "verificato"} | arguments
    result = box.call("t", tool, arguments)
    assert result["is_error"]
    assert result["content"].startswith(f"{arguments['check']} {refusal}")


def rendered(box: Toolbox, tool_id: str, path: str, zooms: list[list[float]] | None = None) -> list[str]:
    result = box.call(tool_id, "render", {"path": path, "zooms": zooms or []})
    proofs: list[str] = json.loads(result["content"])["proofs"]
    return proofs


def test_observe_refuses_a_render_viewed_for_an_older_version(tmp_path: Path) -> None:
    """The critic viewed the red version's render. The black version was rendered and never viewed."""
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    (proof,) = rendered(box, "r1", "a.png")
    box.call("v1", "view_image", {"path": proof})
    Image.new("RGB", (100, 100), (0, 0, 0)).save(work / "a.png")
    rendered(box, "r2", "a.png")

    result = box.call("o1", "observe", {"file": "a.png", "seen": SEEN_RED})

    assert result.get("is_error")
    assert "non hai guardato un render della versione attuale" in str(result["content"])


def test_same_stem_sources_get_distinct_proofs(tmp_path: Path) -> None:
    """Each source has its own proof, so viewing x.jpg's render cannot back evidence for x.png."""
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "x.png")
    Image.new("RGB", (100, 100), (30, 30, 200)).save(work / "x.jpg")
    png = rendered(box, "r1", "x.png")
    jpg = rendered(box, "r2", "x.jpg")
    box.call("v1", "view_image", {"path": jpg[0]})

    assert png != jpg
    assert box.call("o1", "observe", {"file": "x.png", "seen": SEEN_RED}).get("is_error")


def test_two_zooms_with_one_corner_get_two_files(tmp_path: Path) -> None:
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (400, 400), (200, 30, 30)).save(work / "a.png")

    proofs = rendered(box, "r1", "a.png", zooms=[[0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.8, 0.8]])

    assert len(proofs) == 3 and len(set(proofs)) == 3
    with Image.open(work / proofs[1]) as small, Image.open(work / proofs[2]) as large:
        assert small.size == (40, 40)
        assert large.size == (320, 320)


@needs_craft
def test_reviewer_delivers_without_owning_a_master(tmp_path: Path) -> None:
    config = settings(tmp_path)
    work = config.projects_dir / "p/work"
    work.mkdir(parents=True)
    (work / "reviews").mkdir()
    (work / "reviews/critica.md").write_text("referto")
    spec = TicketSpec(
        title="Critica",
        request="Giudica",
        type=TicketType.REVIEW,
        sender="design-director",
        assignee="critic",
        outputs=["reviews/critica.md"],
        checks={"*.svg": ["critique"]},
        media=[Medium.VECTOR],
    )
    run, _, ledger = runner(config, [turn(use("deliver", "t1", note="regge", verdict="REVISE"))])
    ticket = ledger.open(spec, "p")
    assert run.run(ticket).state == "delivered"


def test_observe_accepts_an_image_really_viewed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    Image.new("RGB", (100, 100), (20, 90, 200)).save(tmp_path / "tavola.png")
    ledger = Ledger(config.layout.ledger)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    box = Toolbox(context)
    arguments = {
        "file": "tavola.png",
        "seen": "Tavola azzurra piena, bordi netti, nessun elemento o difetto.",
    }
    assert box.call("a", "observe", arguments)["is_error"]
    box.call("b", "view_image", {"path": "tavola.png"})
    assert not box.call("c", "observe", arguments).get("is_error")


def test_redelivery_with_identical_outputs_is_refused(tmp_path: Path) -> None:
    from agency.contracts.ticket import Action

    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "nota.md").write_text("v1")
    ledger = Ledger(config.layout.ledger)
    spec = TicketSpec(
        title="Nota",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="copywriter",
        outputs=["nota.md"],
        checks={"*.md": ["req:letta"]},
        media=[Medium.NONE],
        medium_why="solo un testo di prova",
    )
    ticket = ledger.open(spec, "p")
    context = ToolContext(
        "copywriter",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    box = Toolbox(context)
    box.call(
        "a", "record_requirement", {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    )
    assert not box.call("b", "deliver", {"note": "prima", "verdict": None}).get("is_error")
    ledger.apply(ticket, Action.REWORK, "design-director", "cambia il titolo")
    context.finished = None
    assert "identici" in box.call("c", "deliver", {"note": "uguale", "verdict": None})["content"]
    (work / "nota.md").write_text("v2")
    box.call(
        "d", "record_requirement", {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    )
    assert not box.call("e", "deliver", {"note": "corretta", "verdict": None}).get("is_error")
