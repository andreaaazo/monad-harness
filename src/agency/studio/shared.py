"""What the slices' graph nodes share: the graph state, the crew they work with, and the helpers more
than one slice uses (ADR-0057)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict

from langgraph.types import Send

from agency.config import Settings
from agency.contracts.outcome import Outcome
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import TicketType
from agency.ledger import Ledger
from agency.workshop.files import read_under, replace_under


class ProjectState(TypedDict):
    """The graph's state, kept in the checkpoint. Any `outcome` text ends the run; `route` is a node's choice
    of the next one."""

    project: str
    root: str
    round: int
    client_note: str
    outcome: str
    explore: bool
    exploration: int
    chosen: str
    route: str


class Runner(Protocol):
    """What the graph asks of the agents: one instance on a ticket. `AgentRunner` is one."""

    def run(
        self, ticket_id: str, attempt: int = 1, rework_note: str = "", mode: str = "", exploration: int = 0
    ) -> Outcome: ...


@dataclass(frozen=True)
class Crew:
    """What the nodes work with: who runs the agents, the registry and the settings."""

    runner: Runner
    ledger: Ledger
    settings: Settings

    def work_dir(self, project: str) -> Path:
        return self.settings.work_dir(parse_project_name(project))


class Node(Protocol):
    """A graph node. LangGraph passes the state by the name `state`, so the protocol names it."""

    def __call__(self, state: Any) -> dict: ...


type Router = Callable[[ProjectState], list[Send] | str]


def attempt(ledger: Ledger, ticket: str) -> int:
    return 1 + sum(1 for event in ledger.history(ticket) if event.action in ("rework", "resume"))


def rework_note(ledger: Ledger, ticket: str) -> str:
    return next((e.note for e in reversed(ledger.history(ticket)) if e.action == "rework"), "")


def copy_capped(work: Path, source: str, target: str, limit: int) -> None:
    """A copy inside the work folder: a sandbox may leave a link at either end, and none is followed.

    The source is read whole, so a file over `limit` is refused."""
    replace_under(work, target, read_under(work, source, limit))


def proposal_tickets(crew: Crew, state: ProjectState) -> list[str]:
    suffix = f"r{state['exploration']}"
    return [
        ticket
        for ticket in crew.ledger.children(state["root"])
        if crew.ledger.spec(ticket).type is TicketType.PROPOSAL
        and crew.ledger.spec(ticket).title.endswith(suffix)
    ]
