"""Assembla i pezzi di una sessione di lavoro. I test ci passano un trasporto registrato."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agency.agents.loop import AgentRunner
from agency.config import Settings
from agency.contracts.run import RunCommand
from agency.contracts.ticket import TicketSpec, TicketType
from agency.gateway import AnthropicTransport, ModelGateway, Transport
from agency.graph.workflow import build
from agency.ledger import Ledger
from agency.ledger.store import BUSY_SECONDS
from agency.qa import delivery
from agency.telemetry import configure, fingerprint
from agency.tools.craft import CommandIndex
from agency.tools.files import sha256

# Valore tecnico richiesto da LangGraph, irraggiungibile: a fermare il lavoro è solo il budget del cliente.
GRAPH_STEPS = 100_000


@dataclass
class Session:
    settings: Settings
    ledger: Ledger
    graph: object
    gateway: ModelGateway

    def _config(self, project: str) -> dict:
        return {
            "configurable": {"thread_id": project},
            "recursion_limit": GRAPH_STEPS,
            "max_concurrency": self.settings.max_parallel,
        }

    def _record(self, project: str, command: RunCommand) -> None:
        """Prima che il grafo lavori: anche un'esecuzione interrotta dal budget ha la sua impronta."""
        choice = self.ledger.project(project)
        model, effort = (choice.model, choice.effort) if choice else ("", "")
        run = self.ledger.record_run(project, command, fingerprint.take(self.settings, model, effort))
        self.gateway.belongs_to(run)

    def start(
        self,
        project: str,
        brief: Path,
        outputs: list[str],
        checks: dict[str, list[str]],
        explore: bool = True,
        budget: float | None = None,
        model: str = "",
        effort: str = "",
    ) -> dict:
        work = self.settings.project_dir(project) / "work"
        work.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(brief, work / "brief.md")
        self.ledger.set_project(project, budget or self.settings.project_budget_usd, model, effort)
        spec = TicketSpec(
            title=f"Consegna {project}",
            request=brief.read_text(encoding="utf-8"),
            type=TicketType.DELIVERY,
            sender="router",
            assignee="design-director",
            outputs=outputs,
            checks=checks,
            inputs=["brief.md"],
            exempt={"construction.md": "documento di costruzione, verificato dal critico con il segno"},
        )
        delivery.validate(spec)
        root = self.ledger.open(spec, project, {"brief.md": sha256(work / "brief.md")})
        state = {
            "project": project,
            "root": root,
            "round": 0,
            "client_note": "",
            "outcome": "",
            "explore": explore,
            "exploration": 0,
            "chosen": "",
            "route": "",
        }
        self._record(project, RunCommand.RUN)
        return self.graph.invoke(state, self._config(project))  # type: ignore[attr-defined]

    def resume(self, project: str) -> dict:
        self._record(project, RunCommand.RESUME)
        return self.graph.invoke(None, self._config(project))  # type: ignore[attr-defined]

    def decide(self, project: str, approved: bool, text: str, choice: str = "") -> dict:
        command = Command(resume={"approved": approved, "text": text, "choice": choice})
        self._record(project, RunCommand.DECIDE)
        return self.graph.invoke(command, self._config(project))  # type: ignore[attr-defined]

    def pending(self, project: str) -> list[dict]:
        state = self.graph.get_state(self._config(project))  # type: ignore[attr-defined]
        return [item.value for task in state.tasks for item in task.interrupts]


def open_session(settings: Settings, transport: Transport | None = None) -> Session:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure(settings.data_dir)
    ledger = Ledger(settings.ledger_path)
    if transport is None:
        key = settings.anthropic_api_key
        transport = AnthropicTransport(key.get_secret_value() if key else None)
    gateway = ModelGateway(transport, ledger, settings)
    index = CommandIndex.load(settings.data_dir / "craft-index")
    runner = AgentRunner(gateway, ledger, settings, index)
    connection = sqlite3.connect(settings.checkpoints_path, check_same_thread=False, timeout=BUSY_SECONDS)
    graph = build(runner, ledger, settings, SqliteSaver(connection))
    return Session(settings, ledger, graph, gateway)
