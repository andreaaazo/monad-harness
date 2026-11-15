"""The exploration with real Craft and recorded answers: directions, levers, sketches and their warnings."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from agency.agents.toolbox import TOOLS, Toolbox, tools_for
from agency.artifacts import FileStore
from agency.contracts.ledger import ConceptEntry
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, Status, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.process.session import open_session
from agency.toolkit.base import ToolContext
from agency.workshop import board
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Sandbox
from support.rules import RULES
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    OUTPUTS,
    Router,
    board_turns,
    brief,
    card,
    context,
    exploration,
    explorer_turns,
    plan_arguments,
    plan_turn,
    to_the_gate,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_explorers_think_and_draw_in_one_instance(tmp_path: Path) -> None:
    transport = Router(to_the_gate())
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.spec("T-0002").outputs) == 4
    names = {tool["name"] for tool in transport.requests["T-0002"][0]["tools"]}
    assert {"craft_run", "view_image", "submit_concept"} <= names
    assert "Cerchi un segno **disegnando**" in transport.requests["T-0002"][0]["system"][0]["text"]


def test_effort_can_be_lowered_to_medium(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path, explorer_effort="medium"), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert transport.requests["T-0003"][0]["output_config"] == {"effort": "medium"}


def test_explorer_cannot_close_without_having_looked(tmp_path: Path) -> None:
    script = {"T-0001:plan": plan_turn(2)}
    script["T-0002"] = [
        turn(use("submit_concept", **card("Solo parole"))),
        turn(use("block", reason="prova")),
    ]
    script["T-0003"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    refused = transport.requests["T-0002"][1]["messages"][-1]["content"][0]
    assert refused["is_error"] and "consegna rifiutata" in refused["content"]


def test_five_directions_run_together_and_reach_the_board(tmp_path: Path) -> None:
    together = threading.Barrier(5, timeout=20)

    class Meeting(Router):
        def stream(self, params: dict) -> dict:
            key = self.key(params)
            if key in ("T-0002", "T-0003", "T-0004", "T-0005", "T-0006") and not self.requests[key]:
                together.wait()  # it times out unless all five run together
            return super().stream(params)

    script = exploration(count=5)
    script["T-0001:plan"] = plan_turn(5)
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    config = settings(tmp_path)
    session = open_session(config, Meeting(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    concepts = session.ledger.concepts("officina", 1)
    assert sorted(row.anon for row in concepts) == list("VWXYZ")
    assert {session.ledger.spec(row.idea_ticket).assignee for row in concepts} == {
        f"direction-{letter}" for letter in "abcde"
    }
    work = config.project_dir(ProjectName("officina")) / "work"
    with Image.open(work / "board/r1/tavola.png") as image:
        assert max(image.size) <= 1600
    assert sorted(path.stem for path in (work / "board/r1/fogli").glob("*.png")) == list("VWXYZ")


def test_number_of_directions_can_go_back_to_three(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn(5)
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path, explorers=3), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.concepts("officina", 1)) == 3
    assert "Esploratori disponibili: 3" in transport.requests["T-0001:plan"][0]["messages"][0]["content"]


def test_explorers_do_not_see_each_other(tmp_path: Path) -> None:
    script = {
        "T-0001:plan": plan_turn(2),
        "T-0002": [turn(use("read_file", path="../b/brief.md")), turn(use("block", reason="prova finita"))],
        "T-0003": [turn(use("block", reason="prova finita"))],
    }
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    result = transport.requests["T-0002"][1]["messages"][-1]["content"][0]
    assert result["is_error"] and "fuori" in result["content"]


def test_exploration_continues_as_long_as_the_budget_allows(tmp_path: Path) -> None:
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = plan_turn() + plan_turn() + [turn(use("block", reason="prova finita"))]
    empty = {"chosen": [], "reasons": "Nessun segno regge"}
    script["T-0001:select"] = [turn(use("select_concepts", **empty)), turn(use("select_concepts", **empty))]
    script |= {f"T-{6 + n:04d}": explorer_turns("abc"[n]) for n in range(3)}
    script["T-0009"] = board_turns("XYZ", failing="XYZ")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.concepts("officina", 2)) == 3


def test_excluded_cannot_ban_a_client_asset(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    arguments = plan_arguments() | {"excluded": ["sagoma di Merlo nero", "ruota dentata", "chiave inglese"]}
    result = Toolbox(ctx, [TOOLS["plan_exploration"]]).call("a", "plan_exploration", arguments)
    assert result["is_error"] and "risorsa del cliente" in result["content"]


def test_each_lever_goes_to_its_own_direction_in_order(tmp_path: Path) -> None:
    """The first lever goes to direction-a, which draws in folder a under files named a, and so on to e."""
    ctx = context(tmp_path, "design-director")
    ctx.ticket_id = ctx.ledger.open(
        TicketSpec(
            title="Radice",
            request="r",
            type=TicketType.PRODUCTION,
            sender="design-director",
            assignee="design-director",
            outputs=["x.png"],
            checks={"*.png": ["visual_review"]},
            media=[Medium.IMAGE],
        ),
        "p",
    )
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")

    result = Toolbox(ctx, [TOOLS["plan_exploration"]]).call("a", "plan_exploration", plan_arguments(5))

    assert not result.get("is_error"), result
    rows = ctx.ledger.concepts("p", 1)
    assert [(row.letter, row.lever) for row in rows] == [
        ("a", "il nome"),
        ("b", "il gesto"),
        ("c", "la materia"),
        ("d", "le persone"),
        ("e", "la convenzione rovesciata"),
    ]
    specs = [ctx.ledger.spec(row.idea_ticket) for row in rows]
    assert [spec.assignee for spec in specs] == [
        "direction-a",
        "direction-b",
        "direction-c",
        "direction-d",
        "direction-e",
    ]
    assert [(spec.title, spec.workspace, spec.outputs) for spec in specs] == [
        (
            f"Esplorazione {letter.upper()}",
            f"explorations/r1/{letter}",
            ["scheda.json", f"schizzi-{letter}.vectorcraft", f"foglio-{letter}.png", f"schizzo-{letter}.png"],
        )
        for letter in "abcde"
    ]


def test_one_failed_explorer_does_not_stop_the_others(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0002"] = [turn(use("block", reason="Idea impossibile"))]
    script["T-0005"] = board_turns("YZ")
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert sorted(row.anon for row in session.ledger.concepts("officina", 1) if row.anon) == ["Y", "Z"]


def test_interrupted_exploration_resumes_without_repeating_work(tmp_path: Path) -> None:
    config = settings(tmp_path)
    script = to_the_gate()

    class Dies(Router):
        def stream(self, params: dict) -> dict:
            if self.key(params) == "T-0005":
                raise ConnectionError("process killed")
            return super().stream(params)

    dying = Dies(script)
    session = open_session(config, dying)
    with pytest.raises(ConnectionError):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    done = {key: len(value) for key, value in dying.requests.items()}
    again = Router(script)
    second = open_session(config, again)
    second.resume("officina")
    assert second.pending("officina")[0].gate == "concept"
    assert not set(done) & set(again.requests)
    assert len(second.ledger.tickets("officina")) == 7


def write_sketch(path: Path, *boxes: tuple[int, int, int, int], background: str = "white") -> None:
    image = Image.new("RGB", (1200, 800), background)
    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.ellipse(box, fill=(17, 17, 17))
    image.save(path)


def test_board_refuses_nothing_on_a_single_mark(tmp_path: Path) -> None:
    write_sketch(tmp_path / "uno.png", (200, 100, 1000, 700))
    assert board.mark_problem(tmp_path / "uno.png") is None


def test_board_spots_variants_in_the_sketch(tmp_path: Path) -> None:
    write_sketch(
        tmp_path / "tanti.png",
        (20, 300, 240, 520),
        (320, 300, 540, 520),
        (620, 300, 840, 520),
        (920, 300, 1140, 520),
    )
    assert "segni separati" in (board.mark_problem(tmp_path / "tanti.png") or "")


def test_board_ignores_a_light_background(tmp_path: Path) -> None:
    write_sketch(tmp_path / "fondo.png", (500, 300, 700, 500), background="#f4f1ea")
    board.build([("V", tmp_path / "fondo.png")], tmp_path / "tavola.png")
    with Image.open(tmp_path / "tavola.png") as image:
        outside_the_mark = image.convert("RGB").getpixel((65, 145))  # it was beige, inside the frame
    assert outside_the_mark == (255, 255, 255)


def test_explorer_is_warned_once_then_can_insist(tmp_path: Path) -> None:
    """It is an estimate: a real mark in several parts must not stay blocked."""
    ledger = Ledger(tmp_path / "l.sqlite")
    spec = TicketSpec(
        title="Esplorazione A",
        request="Cerca",
        type=TicketType.SKETCH,
        sender="design-director",
        assignee="direction-a",
        outputs=["scheda.json", "schizzo-a.png"],
        checks={"*.png": ["req:forma"]},
        exempt={"scheda.json": "la giudicano critico e direttore"},
        media=[Medium.NONE],
        medium_why="prova senza master",
    )
    concept = ConceptEntry(project="p", round=1, letter="a", lever="il nome", idea_ticket="")
    ticket = ledger.open(spec, "p", concept=concept)
    work = tmp_path / "work"
    work.mkdir()
    write_sketch(work / "schizzo-a.png", (20, 300, 240, 520), (920, 300, 1140, 520))
    ctx = ToolContext(
        "direction-a",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        settings=settings(tmp_path),
        rules=RULES,
    )
    toolbox = Toolbox(ctx, tools_for(RULES, "direction-a", spec))
    evidence = {
        "file": "schizzo-a.png",
        "check": "req:forma",
        "result": "PASS",
        "note": "un segno in due parti",
    }
    Toolbox(ctx, [TOOLS["record_requirement"]]).call("e1", "record_requirement", evidence)
    first = toolbox.call("s1", "submit_concept", card("Due parti"))
    assert first.get("is_error")
    assert "segni separati" in first["content"]
    second = toolbox.call("s2", "submit_concept", card("Due parti"))
    assert not second.get("is_error")
    assert ledger.status(ticket)[0] is Status.DELIVERED
