"""The no-follow helpers at the concept gate, in the agent loop and in Session.start."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agency.agents.loop import AgentRunner
from agency.artifacts import FileStore
from agency.contracts.gate import Decision
from agency.contracts.outcome import Outcome
from agency.gateway import ModelGateway
from agency.process import session as runtime
from agency.process.session import Session
from agency.studio.presentation import document
from agency.studio.presentation import nodes as presentation_nodes
from agency.studio.presentation.tools import (
    PresentConcepts,
    ProposalText,
)
from agency.workshop.craft import CommandIndex
from agency.workshop.files import OutsidePerimeter
from support.rules import RULES
from support.safe_files import BRIEF, PROJECT, ROOT_SPEC, Plant, Studio, link_after_write, refused


class Stop(Exception):
    """Raised by the stand-in graph and gateway: the code under test went on past the work folder."""


# concept_gate (2.F22)


def gate_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Studio:
    studio = Studio(tmp_path)
    studio.put(document.pdf_of(1), b"%PDF- la presentazione")
    answer = Decision(approved=False, text="Ancora", choice="").model_dump()
    monkeypatch.setattr(presentation_nodes, "interrupt", lambda _: answer)
    return studio


def concept_state(studio: Studio) -> dict:
    proposal = ProposalText(letter="Z", title="Il merlo", idea="Idea", why="Perché", risk="Limite")
    note = PresentConcepts(proposals=[proposal], recommended="Z", reasons="Regge").model_dump_json()
    return studio.state() | {"client_note": note}


def test_the_concept_gate_records_the_hash_of_the_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = gate_studio(tmp_path, monkeypatch)

    studio.node("concept_gate")(concept_state(studio))

    (gate,) = studio.ledger.gates(PROJECT)
    digest = hashlib.sha256(b"%PDF- la presentazione").hexdigest()
    assert json.loads(gate.files_json) == {document.pdf_of(1): digest}


@pytest.mark.parametrize("planted", [("presentation", ""), (document.pdf_of(1), "secret.txt")])
def test_the_concept_gate_refuses_a_linked_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: Plant
) -> None:
    studio = gate_studio(tmp_path, monkeypatch)
    refused(studio, lambda: studio.node("concept_gate")(concept_state(studio)), planted)
    assert studio.ledger.gates(PROJECT) == []


# The agent loop (2.F1)


class Gateway:
    def call(self, *_: object) -> object:
        raise Stop

    def run(self, *_: object, **__: object) -> object:
        raise Stop


def runner_for(studio: Studio, workspace: str, tmp_path: Path) -> Callable[[], Outcome]:
    spec = ROOT_SPEC.model_copy(update={"workspace": workspace})
    ticket = studio.ledger.open(spec, PROJECT)
    gateway: ModelGateway = Gateway()  # type: ignore[assignment]
    runner = AgentRunner(
        gateway, studio.ledger, studio.settings, CommandIndex([]), FileStore(tmp_path / "a"), rules=RULES
    )
    return lambda: runner.run(ticket)


@pytest.mark.parametrize("workspace", ["", "proposals/r1/a"])
def test_the_loop_creates_the_workspace_folder(tmp_path: Path, workspace: str) -> None:
    studio = Studio(tmp_path)

    with pytest.raises(Stop):
        runner_for(studio, workspace, tmp_path)()

    assert (studio.work / workspace).is_dir()


@pytest.mark.parametrize("planted", [("proposals", ""), ("proposals/r1", ""), ("proposals/r1/a", "")])
def test_the_loop_refuses_a_linked_workspace_before_the_sandbox_binds_it(
    tmp_path: Path, planted: Plant
) -> None:
    studio = Studio(tmp_path)
    refused(studio, runner_for(studio, "proposals/r1/a", tmp_path), planted)


# Session.start (2.F2)


class StopGraph:
    def invoke(self, *_: object) -> object:
        raise Stop


def started(studio: Studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], str]:
    monkeypatch.setattr(Session, "_record", lambda *_: None)
    brief = tmp_path / "brief.md"
    brief.write_bytes(BRIEF)
    session = Session(studio.settings, studio.ledger, StopGraph(), MagicMock(), MagicMock(), RULES)  # type: ignore[arg-type]
    outputs_ = ["source/segno.vectorcraft", "exports/segno.svg", "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    return lambda: session.start(PROJECT, brief, outputs_, checks, budget=10.0)


def test_start_replaces_a_brief_linked_in_an_existing_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Studio(tmp_path)
    studio.plant("brief.md", "secret.txt")
    start = started(studio, tmp_path, monkeypatch)

    with pytest.raises(Stop):  # the graph is the next step: the copy went by
        start()

    assert studio.untouched()
    assert (studio.work / "brief.md").read_bytes() == BRIEF
    assert not (studio.work / "brief.md").is_symlink()
    assert studio.ledger.inputs("T-0002")["brief.md"] == hashlib.sha256(BRIEF).hexdigest()


def test_start_refuses_a_brief_swapped_for_a_link_before_it_is_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Studio(tmp_path)
    start = started(studio, tmp_path, monkeypatch)
    link_after_write(monkeypatch, runtime, "brief.md", studio.host / "secret.txt")

    with pytest.raises(OutsidePerimeter):
        start()

    assert studio.untouched()
    assert [t.id for t in studio.ledger.tickets(PROJECT)] == ["T-0001"]
