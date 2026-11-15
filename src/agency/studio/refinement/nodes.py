"""The refinement nodes: the finisher starts from the chosen proposal, the director leads the revisions and
the team works them. The logic is in `application`; these only speak LangGraph."""

from __future__ import annotations

from agency.studio.graph import Node
from agency.studio.refinement.application import direct, open_production, run_team
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def start_production(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return open_production(crew, state)

    return node


def lead(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return direct(crew, state)

    return node


def team(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return run_team(crew, state)

    return node
