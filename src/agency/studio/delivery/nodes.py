"""The delivery node: the client's `final` gate, and the system's acceptance behind it. The logic is in
`application`; this only speaks LangGraph, and the gate's pause is LangGraph's `interrupt`."""

from __future__ import annotations

from langgraph.types import interrupt

from agency.contracts.gate import Decision
from agency.studio.delivery.application import final_gate_request, record_final_decision
from agency.studio.graph import Node
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def client_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        gate = final_gate_request(crew, state)
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        return record_final_decision(crew, state, decision)

    return node
