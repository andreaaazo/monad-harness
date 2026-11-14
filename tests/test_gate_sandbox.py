"""A sandbox that cannot get its scope at the final gate keeps the client's decision and stops cleanly."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agency import cli
from agency.config import Settings
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.graph import workflow
from agency.ledger import Ledger
from agency.qa import delivery
from agency.runtime import Session
from agency.telemetry import report
from agency.workshop.sandbox import SandboxUnavailable

PROJECT = "officina"
REASON = (
    "la sandbox non parte senza i limiti di memoria e processi: systemd-run non esiste su questa macchina"
)
SPEC = TicketSpec(
    title="Consegna",
    request="Un segno",
    type=TicketType.PRODUCTION,
    sender="router",
    assignee="identity-designer",
    outputs=["source/segno.vectorcraft"],
    checks={"*.vectorcraft": ["master_open"]},
    media=[Medium.VECTOR],
)


class Machine:
    """The sandbox scope: unavailable until `fixed` is set."""

    fixed = False

    def acceptance_problems(self, *_: object) -> list[str]:
        if not self.fixed:
            raise SandboxUnavailable(REASON)
        return []


def waiting_at_the_final_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Session, str, Machine]:
    settings = Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "projects", _env_file=None)  # type: ignore[call-arg]
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.set_project(PROJECT, 10.0)
    root = ledger.open(SPEC, PROJECT)
    ledger.apply(root, Action.DELIVER, "identity-designer", "consegna", None, {})
    settings.project_dir(parse_project_name(PROJECT)).mkdir(parents=True)
    graph = workflow.build(MagicMock(), ledger, settings, InMemorySaver())
    session = Session(settings, ledger, graph, MagicMock(), MagicMock())
    state = {
        "project": PROJECT,
        "root": root,
        "round": 0,
        "client_note": "",
        "outcome": "",
        "explore": False,
        "exploration": 0,
        "chosen": "",
        "route": "",
    }
    session.graph.invoke(state, session._config(PROJECT))  # type: ignore[arg-type]
    assert [gate.gate for gate in session.pending(PROJECT)] == ["final"]
    machine = Machine()
    monkeypatch.setattr(delivery, "acceptance_problems", machine.acceptance_problems)
    monkeypatch.setattr(cli, "_report_of", lambda *_: None)
    monkeypatch.setattr(report, "render", lambda _: "rapporto")
    return session, root, machine


def test_the_client_decision_survives_a_sandbox_that_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session, root, machine = waiting_at_the_final_gate(tmp_path, monkeypatch)
    project = parse_project_name(PROJECT)

    code = cli._guarded(project, session, lambda: session.decide(PROJECT, True, "Approvato"))

    out = capsys.readouterr().out
    assert code == 4
    assert "rapporto" in out
    assert f"SANDBOX NON DISPONIBILE: {REASON}. Il lavoro è salvato." in out
    assert f"Per riprendere: agency resume {PROJECT}" in out
    assert session.ledger.status(root)[0] is Status.DELIVERED  # nothing was accepted
    assert session.graph.get_state(session._config(PROJECT)).next == ("client_gate",)  # type: ignore[arg-type]

    machine.fixed = True
    code = cli._guarded(project, session, lambda: session.resume(PROJECT))  # no new decision is asked

    assert code == 0
    assert "Esito: approvato" in capsys.readouterr().out
    assert session.ledger.status(root)[0] is Status.ACCEPTED
    assert session.pending(PROJECT) == []
