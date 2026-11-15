"""What more than one flow test file uses: the scripted turns, the runner, the contexts and the tool boxes."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agency.agents.loop import AgentRunner
from agency.agents.toolbox import TOOLS, Toolbox
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.ledger import ConceptEntry, LedgerPort
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.gateway import ModelGateway
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import (
    Sandbox,
)
from support.rules import RULES
from support.scripted import ScriptedTransport
from support.settings import settings

SVG_PATH = "M10 90 L50 10 L90 90 Z"


needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def use(name: str, tool_id: str, **arguments: object) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def production_spec() -> TicketSpec:
    return TicketSpec(
        title="Segno",
        request="Disegna il segno",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=["source/segno.vectorcraft", "exports/segno.svg"],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
    )


def runner(config: Settings, responses: list[dict]) -> tuple[AgentRunner, ScriptedTransport, Ledger]:
    """Project `p`, with the cap the client would declare: without one the gateway spends nothing
    (ADR-0043)."""
    ledger = Ledger(config.layout.ledger)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(responses)
    index = CommandIndex.load(config.data_dir / "craft-index")
    return (
        AgentRunner(
            ModelGateway(transport, ledger, config),
            ledger,
            config,
            index,
            FileStore(config.layout.artifacts),
            rules=RULES,
        ),
        transport,
        ledger,
    )


def steps() -> list[dict]:
    return [
        {"command": "path.create", "params": {"d": SVG_PATH}},
        {"command": "select.set", "params": {"ids": [2]}},
        {"command": "paint.setStroke", "params": {"none": True}},
        {"command": "paint.setFill", "params": {"color": "#111111"}},
    ]


DIRECTOR = production_spec().model_copy(update={"assignee": "design-director"})


def bare_context(tmp_path: Path, role: str) -> ToolContext:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    artifacts = FileStore(tmp_path / "artifacts")
    inputs = config.layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True, exist_ok=True)
    sandbox = Sandbox(tmp_path, ops=inputs)
    return ToolContext(role, "p", "T-1", "i", ledger, sandbox, CommandIndex([]), artifacts, rules=RULES)


SEEN_RED = "Quadrato rosso pieno, bordi netti, nessun difetto visibile nel render."


def closing_box(
    tmp_path: Path, spec: TicketSpec, actor: str, *tools: str, concept: ConceptEntry | None = None
) -> tuple[Toolbox, ToolContext, str]:
    """A ticket of `spec` open for `actor`, its work folder ready: the toolbox, its context, the ticket. A
    `concept` is opened with it, as plan_exploration opens an idea."""
    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    ledger = Ledger(config.layout.ledger)
    ticket = ledger.open(spec, "p", concept=concept)
    context = ToolContext(
        actor,
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    return Toolbox(context, [TOOLS[name] for name in tools]), context, ticket


def crash_after_the_transition(
    box: Toolbox, context: ToolContext, monkeypatch: pytest.MonkeyPatch, name: str, arguments: dict
) -> None:
    """The process dies once the ledger transition has committed, before the resume record is written."""

    def die(*_: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(context.ledger, "record_operation", die)
        with pytest.raises(KeyboardInterrupt):
            box.call("t1", name, arguments)
    assert context.ledger.operation("i:t1") is None
    context.finished = None  # the process restarts: nothing of the old context survives


def intact(ledger: LedgerPort) -> None:
    """The chain checks are the SQLite ledger's, not the engine's port: the context holds that ledger."""
    assert isinstance(ledger, Ledger)
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []
