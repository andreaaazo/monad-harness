"""The exploration nodes: the director plans the round, the explorers draw in parallel."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END
from langgraph.types import Send

from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE
from agency.studio.shared import Crew, Node, ProjectState, Router, attempt


def plan(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        turn = state["exploration"] + 1
        note = f"Esploratori disponibili: {crew.settings.explorers}. {state['client_note']}"
        outcome = crew.runner.run(state["root"], turn, note.strip(), mode="plan")
        if outcome.state is OutcomeState.BLOCKED:
            return {"exploration": turn, "outcome": f"bloccato: {outcome.note}"}
        return {"exploration": turn, "client_note": ""}

    return node


def send_explorers(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | str:
        if state["outcome"]:
            return END
        rows = crew.ledger.concepts(state["project"], state["exploration"])
        sends = [
            Send("explore", {"ticket": row.idea_ticket})
            for row in rows
            if crew.ledger.status(row.idea_ticket)[0] in RUNNABLE
        ]
        return sends or "make_board"

    return route


def explore(crew: Crew) -> Node:
    def node(state: Any) -> dict:
        crew.runner.run(state["ticket"], attempt(crew.ledger, state["ticket"]))
        return {}

    return node
