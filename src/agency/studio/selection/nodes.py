"""The selection nodes: the anonymous board, the critic's first look and the director's choice. The logic is
in `application`; these only speak LangGraph."""

from __future__ import annotations

from agency.studio.graph import Node
from agency.studio.selection.application import build_board, choose_concepts, review_board
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def make_board(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return build_board(crew, state)

    return node


def board_review(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return review_board(crew, state)

    return node


def select(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return choose_concepts(crew, state)

    return node
