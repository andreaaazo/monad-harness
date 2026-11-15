"""The delivery's use cases, without LangGraph: the node is a thin adapter over them, and the `final` gate's
pause stays in the node (ADR-0058)."""

from __future__ import annotations

from agency.contracts.gate import Decision, FinalGate
from agency.contracts.ticket import Action, Status
from agency.qa import delivery
from agency.studio.delivery.domain import acceptance_refusal
from agency.studio.shared import Crew, ProjectState, ProjectUpdate


def final_gate_request(crew: Crew, state: ProjectState) -> FinalGate:
    """What the client is asked at the `final` gate: the files the work delivered."""
    root = state["root"]
    return FinalGate(ticket=root, files=sorted(crew.ledger.delivered(root)))


def record_final_decision(crew: Crew, state: ProjectState, decision: Decision) -> ProjectUpdate:
    """The client's decision: a request for changes goes back to the director, an approval is accepted only
    if the system finds every delivered file and proof in order."""
    root = state["root"]
    if crew.ledger.status(root)[0] is Status.ACCEPTED:
        return {"outcome": "approvato"}
    if not decision.approved:
        crew.ledger.apply(root, Action.REWORK, "router", decision.text or "il cliente chiede modifiche")
        return {"client_note": decision.text, "outcome": ""}
    project = state["project"]
    problems = delivery.acceptance_problems(crew.ledger, project, crew.sandbox_for(project), root, crew.rules)
    if problems:
        text = acceptance_refusal(problems)
        crew.ledger.apply(root, Action.REWORK, "router", text)
        return {"client_note": text, "outcome": ""}
    crew.ledger.apply(root, Action.ACCEPT, "router", decision.text)
    return {"outcome": "approvato"}
