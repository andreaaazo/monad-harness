"""Assembles the parts of a working session. Tests pass it a recorded transport."""

from __future__ import annotations

import fcntl
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agency.agents.loop import AgentRunner
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.gate import GATE, Decision, Gate
from agency.contracts.project import parse_project_name
from agency.contracts.run import RunCommand
from agency.contracts.ticket import TicketSpec, TicketType
from agency.gateway import AnthropicTransport, ModelGateway, RecordingTransport, Transport
from agency.graph.workflow import Graph, build
from agency.ledger import Ledger
from agency.ledger.store import BUSY_SECONDS
from agency.qa import delivery
from agency.studio.shared import ProjectState
from agency.telemetry import configure, fingerprint
from agency.workshop.craft import CommandIndex
from agency.workshop.files import replace_under, sha256_under

# A technical value LangGraph requires, never reached: only the client's budget stops the work.
GRAPH_STEPS = 100_000


def _outcome(result: dict[str, Any] | None) -> str:
    """The project's outcome from the graph's final state: empty if the work waits for the client.

    LangGraph returns the state as a dict, or nothing if there was nothing to run: this is the boundary.
    """
    return str((result or {}).get("outcome", ""))


class BriefNotUtf8(Exception):
    """The brief file cannot be decoded as UTF-8; raised before anything is written."""


class NothingToResume(Exception):
    """The project has no checkpoint: its first run never got as far as saving one."""


class ProjectBusy(Exception):
    """Another process already holds the project: two workers would pay for every call twice (COR-005)."""


class ProjectLock:
    """A claim that never waits, on a lock file, for as long as the `with` block runs: exclusive, or shared
    with the other shared claims (the registry's, 2.F63).

    `flock` is released by the kernel when the process ends, so a crash never leaves a stale lock.
    """

    def __init__(self, path: Path, shared: bool = False) -> None:
        self.path = path
        self.shared = shared
        self._fd = -1

    def __enter__(self) -> ProjectLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(fd)
            raise ProjectBusy(self.path.stem) from error
        self._fd = fd
        return self

    def __exit__(
        self, kind: type[BaseException] | None, error: BaseException | None, trace: TracebackType | None
    ) -> None:
        os.close(self._fd)
        self._fd = -1


@dataclass
class Session:
    """A working session on the registry and the graph. `start`, `resume` and `decide` each record a run,
    with its fingerprint, before the graph works."""

    settings: Settings
    ledger: Ledger
    graph: Graph
    gateway: ModelGateway
    transport: Transport  # the one `open_session` chose: every recorded run wraps this one, never a recorder
    record: bool = False

    def _config(self, project: str) -> RunnableConfig:
        return {
            "configurable": {"thread_id": project},
            "recursion_limit": GRAPH_STEPS,
            "max_concurrency": self.settings.max_parallel,
        }

    def _record(self, project: str, command: RunCommand) -> None:
        """Before the graph works, so even a run stopped by the budget has its fingerprint."""
        choice = self.ledger.project(project)
        model, effort = (choice.model, choice.effort) if choice else ("", "")
        run = self.ledger.record_run(project, command, fingerprint.take(self.settings, model, effort))
        self.gateway.belongs_to(run)
        if self.record:  # one cassette per run, named after it (ADR-0048)
            cassette = self.settings.layout.cassette(parse_project_name(project), run)
            self.gateway.transport = RecordingTransport(self.transport, cassette)

    def start(
        self,
        project: str,
        brief: Path,
        outputs: list[str],
        checks: dict[str, list[str]],
        *,
        budget: float,
        explore: bool = True,
        model: str = "",
        effort: str = "",
    ) -> str:
        """`budget` is the cap in dollars that whoever starts the project declares: no default (ADR-0043)."""
        folder = parse_project_name(project)  # before anything is read or written (COR-013)
        try:
            request = brief.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise BriefNotUtf8(brief) from error
        spec = TicketSpec(
            title=f"Consegna {project}",
            request=request,
            type=TicketType.DELIVERY,
            sender="router",
            assignee="design-director",
            outputs=outputs,
            checks=checks,
            inputs=["brief.md"],
            exempt={"construction.md": "documento di costruzione, verificato dal critico con il segno"},
        )
        delivery.validate(spec)
        work = self.settings.work_dir(folder)
        work.mkdir(parents=True, exist_ok=True)
        replace_under(work, "brief.md", brief.read_bytes())
        self.ledger.set_project(project, budget, model, effort)
        root = self.ledger.open(spec, project, {"brief.md": sha256_under(work, "brief.md")})
        state = ProjectState(
            project=project,
            root=root,
            round=0,
            client_note="",
            outcome="",
            explore=explore,
            exploration=0,
            chosen="",
            route="",
        )
        self._record(project, RunCommand.RUN)
        return _outcome(self.graph.invoke(state, self._config(project)))

    def resume(self, project: str) -> str:
        if not self.graph.get_state(self._config(project)).values:
            raise NothingToResume(project)
        self._record(project, RunCommand.RESUME)
        return _outcome(self.graph.invoke(None, self._config(project)))

    def decide(self, project: str, approved: bool, text: str, choice: str = "") -> str:
        decision = Decision(approved=approved, text=text, choice=choice)
        self._record(project, RunCommand.DECIDE)
        return _outcome(self.graph.invoke(Command(resume=decision.model_dump()), self._config(project)))

    def pending(self, project: str) -> list[Gate]:
        state = self.graph.get_state(self._config(project))
        return [GATE.validate_python(item.value) for task in state.tasks for item in task.interrupts]


def open_session(settings: Settings, transport: Transport | None = None, record: bool = False) -> Session:
    """Assembles a session: ledger, gateway, agent runner and checkpointed graph.

    `record` writes each run's answers to its cassette under the data root, for replay in tests.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure(settings.layout.traces)
    ledger = Ledger(settings.layout.ledger)
    if transport is None:
        key = settings.anthropic_api_key
        transport = AnthropicTransport(key.get_secret_value() if key else None)
    gateway = ModelGateway(transport, ledger, settings)
    index = CommandIndex.load(settings.layout.craft_index)
    runner = AgentRunner(gateway, ledger, settings, index, FileStore(settings.layout.artifacts))
    connection = sqlite3.connect(settings.layout.checkpoints, check_same_thread=False, timeout=BUSY_SECONDS)
    graph = build(runner, ledger, settings, SqliteSaver(connection))
    return Session(settings, ledger, graph, gateway, transport, record)
