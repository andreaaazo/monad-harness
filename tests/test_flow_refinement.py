"""The refinement with real Craft and recorded answers: the finisher, and a concept the director rejects."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.process.session import open_session
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.files import sha256
from agency.workshop.sandbox import Sandbox
from support.rules import RULES
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    DRAW,
    MASTER,
    OUTPUTS,
    Router,
    brief,
    exploration,
    plan_turn,
    present_turn,
    proposal_turns,
    to_the_gate,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_finisher_starts_from_the_approved_proposal(tmp_path: Path) -> None:
    config = settings(tmp_path)
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="prova finita"))]
    script["T-0001"] = [turn(use("block", reason="prova finita"))]
    session = open_session(config, Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "La Y", "Y")
    work = config.project_dir(ProjectName("officina")) / "work"
    assert (work / MASTER).read_bytes() == (work / "proposals/r1/y/proposta-y.vectorcraft").read_bytes()


def test_finisher_cannot_explore(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    spec = TicketSpec(
        title="Costruzione",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=[MASTER],
        checks={"*.vectorcraft": ["master_open"]},
        media=[Medium.VECTOR],
        prompt="finisher",
    )
    ticket = ledger.open(spec, "p")
    index = CommandIndex.load(tmp_path / "index")
    config = settings(tmp_path)
    inputs = config.layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True)
    sandbox, store = Sandbox(tmp_path, ops=inputs), FileStore(tmp_path / "a")
    ctx = ToolContext(
        "identity-designer", "p", ticket, "i", ledger, sandbox, index, store, settings=config, rules=RULES
    )
    box = Toolbox(ctx)
    refused = box.call("a", "craft_run", {"document": "source/prova.vectorcraft", "steps": DRAW})
    assert refused["is_error"] and "niente file di esplorazione" in refused["content"]
    assert not box.call("b", "craft_run", {"document": MASTER, "steps": DRAW}).get("is_error")


def test_rejected_concept_goes_back_to_exploration(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="Il concetto non regge a piccola scala"))]
    script["T-0001"] = [turn(use("reject_concept", reason="A piccola scala l'idea sparisce del tutto"))]
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    assert "sparisce" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_new_concept_after_a_rejection_gets_its_own_production(tmp_path: Path) -> None:
    """The second finishing ticket starts from the new approved master, not from the first idea's."""
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="Il concetto non regge a piccola scala"))]
    script["T-0001"] = [
        turn(use("reject_concept", reason="A piccola scala l'idea sparisce del tutto")),
        turn(use("block", reason="prova finita")),
    ]
    script["T-0001:plan"] = [*plan_turn(), *plan_turn()]
    script.update(exploration(first=9))
    script["T-0001:select"] = [
        *script["T-0001:select"],
        turn(use("select_concepts", chosen=["Y"], reasons="Si legge da sola")),
    ]
    second = proposal_turns("Y")
    second[1]["content"][0]["input"]["steps"] = [
        {**DRAW[0], "params": {"d": "M10 10 L90 10 L90 90 L10 90 Z"}},
        *DRAW[1:],
    ]
    script["T-0013"] = second
    script["T-0001:present"] = [*script["T-0001:present"], *present_turn("Y", round_=2)]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Mi piace la Y", "Y")
    assert session.ledger.spec("T-0014").prompt == "finisher"
    work = settings(tmp_path).project_dir(ProjectName("officina")) / "work"
    assert sha256(work / MASTER) == sha256(work / "proposals/r2/y/proposta-y.vectorcraft")
