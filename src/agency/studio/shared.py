"""What the slices' graph nodes share: the graph state, the crew they work with, and the helpers more
than one slice uses (ADR-0057). The types LangGraph sees are in `studio.graph` (ADR-0058)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol, TypedDict

from agency.config import Settings
from agency.contracts.ledger import LedgerPort, Tickets
from agency.contracts.outcome import Outcome
from agency.contracts.phase import DirectorMode
from agency.contracts.project import parse_project_name
from agency.contracts.registry import StudioRules
from agency.contracts.sandbox import SandboxPort
from agency.contracts.ticket import TicketType
from agency.workshop.files import read_under, replace_under

# Every value a router returns and every value `ProjectState.route` holds: the 13 nodes, the director's
# rejection of a concept, LangGraph's end, and no choice. Checkpoints already hold these strings (ADR-0058).
type Route = Literal[
    "plan",
    "explore",
    "make_board",
    "board_review",
    "select",
    "prepare_proposals",
    "proposal",
    "present",
    "concept_gate",
    "start_production",
    "lead",
    "team",
    "client_gate",
    "rejected",
    "__end__",
    "",
]
# LangGraph's END, so the slices can end the run without importing LangGraph; a test checks the value.
END_ROUTE: Final = "__end__"


class TicketPayload(TypedDict):
    """What a node reached by `Send` receives: the ticket it works on."""

    ticket: str


# The node is annotated with this alias, not with the class: LangGraph turns a class annotation into an
# input schema and adds a channel to the checkpoint, while an alias is not a class and leaves the node on
# the state. Pyright still sees the TypedDict, which LangGraph's typing requires. A test pins the graph's
# shape (ADR-0058).
type TicketTask = TicketPayload


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
    route: Route


class ProjectUpdate(TypedDict, total=False):
    """What a node changes in the state: any of its fields, and only those."""

    project: str
    root: str
    round: int
    client_note: str
    outcome: str
    explore: bool
    exploration: int
    chosen: str
    route: Route


class Runner(Protocol):
    """What the graph asks of the agents: one instance on a ticket. `AgentRunner` is one."""

    def run(
        self,
        ticket_id: str,
        attempt: int = 1,
        rework_note: str = "",
        mode: DirectorMode | None = None,
        exploration: int = 0,
    ) -> Outcome: ...


@dataclass(frozen=True)
class Crew:
    """What the nodes work with: who runs the agents, the registry, the settings, the studio rules and a
    project's sandbox."""

    runner: Runner
    ledger: LedgerPort
    settings: Settings
    rules: StudioRules
    sandbox_for: Callable[[str], SandboxPort]  # a project's sandbox, for the acceptance at the final gate

    def work_dir(self, project: str) -> Path:
        return self.settings.work_dir(parse_project_name(project))


def attempt(ledger: Tickets, ticket: str) -> int:
    return 1 + sum(1 for event in ledger.history(ticket) if event.action in ("rework", "resume"))


def rework_note(ledger: Tickets, ticket: str) -> str:
    return next((e.note for e in reversed(ledger.history(ticket)) if e.action == "rework"), "")


def copy_capped(work: Path, source: str, target: str, limit: int) -> None:
    """A copy inside the work folder: a sandbox may leave a link at either end, and none is followed.

    The source is read whole, so a file over `limit` is refused."""
    replace_under(work, target, read_under(work, source, limit))


def proposal_title(anon: str, turn: int) -> str:
    """A proposal ticket's title: the proposal slice opens it, the presentation finds it by it."""
    return f"Proposta {anon} r{turn}"


def proposal_tickets(crew: Crew, state: ProjectState) -> list[str]:
    suffix = f"r{state['exploration']}"
    return [
        ticket
        for ticket in crew.ledger.children(state["root"])
        if crew.ledger.spec(ticket).type is TicketType.PROPOSAL
        and crew.ledger.spec(ticket).title.endswith(suffix)
    ]
