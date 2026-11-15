"""The exploration's use cases, without LangGraph: the nodes and the router are thin adapters over them
(ADR-0058)."""

from __future__ import annotations

from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE
from agency.studio.exploration.domain import plan_note
from agency.studio.shared import END_ROUTE, Crew, ProjectState, ProjectUpdate, Route, attempt


def start_round(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The director plans a new round of exploration, with what the client said last."""
    turn = state["exploration"] + 1
    note = plan_note(crew.settings.explorers, state["client_note"])
    outcome = crew.runner.run(state["root"], turn, note, mode="plan")
    if outcome.state is OutcomeState.BLOCKED:
        return {"exploration": turn, "outcome": f"bloccato: {outcome.note}"}
    return {"exploration": turn, "client_note": ""}


def explorers_to_run(crew: Crew, state: ProjectState) -> list[str] | Route:
    """The idea tickets of this round that still have work to do, or where the graph goes without them."""
    if state["outcome"]:
        return END_ROUTE
    rows = crew.ledger.concepts(state["project"], state["exploration"])
    tickets = [row.idea_ticket for row in rows if crew.ledger.status(row.idea_ticket)[0] in RUNNABLE]
    return tickets or "make_board"


def explore_one(crew: Crew, ticket: str) -> None:
    """One explorer works on its idea ticket, as a new attempt after each rework."""
    crew.runner.run(ticket, attempt(crew.ledger, ticket))
