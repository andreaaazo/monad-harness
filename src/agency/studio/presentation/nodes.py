"""The presentation nodes: the director presents the proposals, and the client chooses at the `concept` gate.
The logic is in `application`; these only speak LangGraph, and the gate's pause is LangGraph's `interrupt`."""

from __future__ import annotations

from langgraph.types import interrupt

from agency.contracts.gate import Decision
from agency.studio.graph import Node
from agency.studio.presentation.application import (
    concept_gate_request,
    present_proposals,
    record_concept_decision,
)
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def present(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        return present_proposals(crew, state)

    return node


def concept_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        gate = concept_gate_request(crew, state)
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        return record_concept_decision(crew, state, gate, decision)

    return node
