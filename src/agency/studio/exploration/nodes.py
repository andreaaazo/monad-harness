"""The exploration nodes: the director plans the round, the explorers draw in parallel. The logic is in
`application`; these only speak LangGraph."""

from __future__ import annotations

from langgraph.types import Send

from agency.studio.exploration.application import explore_one, explorers_to_run, start_round
from agency.studio.graph import Node, Router, TaskNode
from agency.studio.shared import Crew, ProjectState, ProjectUpdate, Route, TicketTask


def plan(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return start_round(crew, state)

    return node


def send_explorers(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | Route:
        found = explorers_to_run(crew, state)
        if isinstance(found, list):
            return [Send("explore", {"ticket": ticket}) for ticket in found]
        return found

    return route


def explore(crew: Crew) -> TaskNode:
    def node(state: TicketTask) -> ProjectUpdate:
        explore_one(crew, state["ticket"])
        return {}

    return node
