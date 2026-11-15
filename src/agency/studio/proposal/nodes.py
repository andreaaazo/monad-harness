"""The proposal nodes: each chosen idea becomes a proposal, developed in parallel. The logic is in
`application`; these only speak LangGraph."""

from __future__ import annotations

from langgraph.types import Send

from agency.studio.graph import Node, Router, TaskNode
from agency.studio.proposal.application import develop, open_proposals, proposals_to_run
from agency.studio.shared import Crew, ProjectState, ProjectUpdate, Route, TicketTask


def prepare_proposals(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return open_proposals(crew, state)

    return node


def send_proposals(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | Route:
        found = proposals_to_run(crew, state)
        if isinstance(found, list):
            return [Send("proposal", {"ticket": ticket}) for ticket in found]
        return found

    return route


def proposal(crew: Crew) -> TaskNode:
    def node(state: TicketTask) -> ProjectUpdate:
        develop(crew, state["ticket"])
        return {}

    return node
