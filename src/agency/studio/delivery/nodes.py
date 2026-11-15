"""The delivery node: the client's `final` gate, and the system's acceptance behind it."""

from __future__ import annotations

from langgraph.types import interrupt

from agency.contracts.gate import Decision, FinalGate
from agency.contracts.ticket import Action, Status
from agency.qa import delivery
from agency.studio.graph import Node
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def client_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        root = state["root"]
        gate = FinalGate(ticket=root, files=sorted(crew.ledger.delivered(root)))
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        if crew.ledger.status(root)[0] is Status.ACCEPTED:
            return {"outcome": "approvato"}
        if not decision.approved:
            crew.ledger.apply(root, Action.REWORK, "router", decision.text or "il cliente chiede modifiche")
            return {"client_note": decision.text, "outcome": ""}
        project = state["project"]
        sandbox = crew.sandbox_for(project)
        problems = delivery.acceptance_problems(crew.ledger, project, sandbox, root, crew.rules)
        if problems:
            text = "Accettazione rifiutata dal sistema:\n" + "\n".join(problems[:12])
            crew.ledger.apply(root, Action.REWORK, "router", text)
            return {"client_note": text, "outcome": ""}
        crew.ledger.apply(root, Action.ACCEPT, "router", decision.text)
        return {"outcome": "approvato"}

    return node
