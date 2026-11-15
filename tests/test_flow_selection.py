"""The selection with real Craft and recorded answers: the anonymous board, the first look and the choice."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from agency.agents.toolbox import TOOLS, Toolbox
from agency.contracts.ledger import ConceptEntry
from agency.contracts.project import ProjectName
from agency.process.session import open_session
from agency.workshop import board
from support.concepts import open_idea
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    OUTPUTS,
    Router,
    board_turns,
    brief,
    context,
    exploration,
    plan_turn,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_board_letters_are_stable_and_shuffled_by_project() -> None:
    first = board.assign_letters("merlo", 1, ["a", "b", "c"])
    assert first == board.assign_letters("merlo", 1, ["a", "b", "c"])
    assert sorted(first.values()) == ["X", "Y", "Z"]
    seen = {tuple(board.assign_letters(f"p{n}", 1, ["a", "b", "c"]).values()) for n in range(20)}
    assert len(seen) > 1


def test_board_gives_every_sketch_the_same_space_and_fits_the_limit(tmp_path: Path) -> None:
    small = Image.new("RGB", (612, 792), (255, 255, 255))
    small.paste((0, 0, 0), (290, 380, 320, 410))
    small.save(tmp_path / "piccolo.png")
    output = tmp_path / "tavola.png"
    board.build([(letter, tmp_path / "piccolo.png") for letter in "VWXYZ"], output)
    with Image.open(output) as image:
        assert max(image.size) <= 1600
        gray = image.convert("L")
    cell = gray.crop((30, 40, 510, 520))
    assert cell.point([255] * 128 + [0] * 128).histogram()[255] > 80_000


def test_critic_judges_blind(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0005"] = [
        turn(use("read_file", path="schede.md")),
        turn(use("read_file", path="../../explorations/r1/a/scheda.json")),
        *board_turns(),
    ]
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    requests = transport.requests["T-0005"]
    assert requests[1]["messages"][-1]["content"][0]["is_error"]
    assert requests[2]["messages"][-1]["content"][0]["is_error"]


def test_every_letter_must_be_rated(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptEntry(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    box = Toolbox(ctx, [TOOLS["rate_board"]])
    partial = {"ratings": [{"letter": "X", "first_look": "Un merlo", "passes": True}]}
    assert box.call("a", "rate_board", partial)["is_error"]


def test_director_cannot_choose_what_failed_the_first_look(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptEntry(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    box = Toolbox(ctx, [TOOLS["select_concepts"]])
    assert box.call("a", "select_concepts", {"chosen": ["X"], "reasons": "r"})["is_error"]
    verdicts = settings(tmp_path).layout.ratings(ProjectName("p"), 1)
    verdicts.parent.mkdir(parents=True)
    rated = [
        {"letter": "X", "first_look": "Un tasto", "passes": False},
        {"letter": "Y", "first_look": "Un merlo", "passes": True},
    ]
    verdicts.write_text(json.dumps(rated))
    refused = box.call("b", "select_concepts", {"chosen": ["X", "Y"], "reasons": "r"})
    assert refused["is_error"] and "primo sguardo" in refused["content"]
    assert not box.call("c", "select_concepts", {"chosen": ["Y"], "reasons": "r"}).get("is_error")


def test_nothing_passes_the_first_look_starts_a_new_exploration(tmp_path: Path) -> None:
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    script["T-0001:select"] = [turn(use("select_concepts", chosen=[], reasons="Nessun segno regge"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert "Nessun segno regge" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_select_refuses_unknown_letters(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    open_idea(ctx.ledger, ConceptEntry(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X"))
    box = Toolbox(ctx, [TOOLS["select_concepts"]])
    assert box.call("a", "select_concepts", {"chosen": ["Q"], "reasons": "perché sì"})["is_error"]


def test_select_concepts_refuses_more_than_three(tmp_path: Path) -> None:
    """Every letter passed the first look, so only the limit of three stops this choice."""
    ctx = context(tmp_path, "design-director")
    anons = {"a": "W", "b": "X", "c": "Y", "d": "Z"}
    for letter, anon in anons.items():
        open_idea(
            ctx.ledger,
            ConceptEntry(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    verdicts = settings(tmp_path).layout.ratings(ProjectName("p"), 1)
    verdicts.parent.mkdir(parents=True)
    passed = [{"letter": anon, "first_look": "Un segno", "passes": True} for anon in anons.values()]
    verdicts.write_text(json.dumps(passed))
    box = Toolbox(ctx, [TOOLS["select_concepts"]])

    result = box.call("a", "select_concepts", {"chosen": list(anons.values()), "reasons": "tutte reggono"})

    assert result["is_error"]
    assert result["content"] == "si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto"


def test_second_exploration_is_rated_on_its_own_letters(tmp_path: Path) -> None:
    """A second round with fewer levers has letters other than the first's: the critic must see the right
    ones."""
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = [*plan_turn(), *plan_turn(2)]
    script.update(exploration(first=6, count=2))
    script["T-0001:select"] = [
        turn(use("select_concepts", chosen=[], reasons="Nessun segno regge")),
        turn(use("block", reason="prova finita")),
    ]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    work = settings(tmp_path).project_dir(ProjectName("officina")) / "work"
    rated = json.loads((work / "board/r2/reviews/valutazione.json").read_text())
    assert {item["letter"] for item in rated} == {"Y", "Z"}
