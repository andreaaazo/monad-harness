"""The presentation's use cases, without LangGraph: the nodes are thin adapters over them, and the `concept`
gate's pause stays in the node (ADR-0058)."""

from __future__ import annotations

import json

from agency.contracts.clock import now
from agency.contracts.concept import ConceptCard, ConceptStatus
from agency.contracts.gate import ConceptGate, Decision
from agency.contracts.ledger import GateEntry
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import Action, Status
from agency.studio.presentation import document
from agency.studio.presentation.domain import concept_choice, proposals_digest
from agency.studio.presentation.tools import PresentConcepts
from agency.studio.shared import (
    END_ROUTE,
    Crew,
    ProjectState,
    ProjectUpdate,
    proposal_tickets,
    proposal_title,
)
from agency.workshop.files import sha256_under


def present_proposals(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The developed proposals are accepted and laid out on one view each; the director drafts the pages."""
    project, turn, root = state["project"], state["exploration"], state["root"]
    concepts = {
        proposal_title(row.anon, turn): row for row in crew.ledger.concepts(project, turn) if row.anon
    }
    shown: list[tuple[str, str, ConceptCard]] = []
    for ticket in proposal_tickets(crew, state):
        status, _ = crew.ledger.status(ticket)
        title = crew.ledger.spec(ticket).title
        if status is Status.DELIVERED:
            crew.ledger.apply(ticket, Action.ACCEPT, "design-director", "pronta per la presentazione")
        if crew.ledger.status(ticket)[0] is not Status.ACCEPTED:
            continue
        row = concepts[title]
        crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.PROPOSAL)
        mark, applications = document.proposal_files(
            crew.work_dir(project), turn, row.anon, crew.ledger.delivered(ticket)
        )
        view = f"proposals/r{turn}/insieme-{row.anon.lower()}.png"
        document.sheet(mark, applications, crew.work_dir(project) / view)
        shown.append((row.anon, view, ConceptCard.model_validate_json(row.card_json)))
    ready = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.PROPOSAL]
    if not ready:
        return {"route": END_ROUTE, "outcome": "bloccato: nessuna proposta è stata sviluppata"}
    outcome = crew.runner.run(root, turn, proposals_digest(shown), mode="present")
    if outcome.state is OutcomeState.PRESENTED:  # the PDF exists, and the director viewed every page
        return {"route": "concept_gate", "client_note": outcome.note}
    if outcome.state is OutcomeState.NO_CONCEPT:
        reasons = PresentConcepts.model_validate_json(outcome.note).reasons
        return {"route": "plan", "client_note": f"Le proposte non reggono: {reasons}"}
    return {"route": END_ROUTE, "outcome": f"bloccato: {outcome.note[:300]}"}


def concept_gate_request(crew: Crew, state: ProjectState) -> ConceptGate:
    """What the client is asked at the `concept` gate: the presentation, the options and the studio's pick."""
    selection = PresentConcepts.model_validate_json(state["client_note"])
    if selection.recommended is None:  # draft_presentation refuses a draft without a recommendation
        raise ValueError("a presentation without a recommendation never reaches the gate")
    return ConceptGate(
        ticket=state["root"],
        files=[document.pdf_of(state["exploration"])],
        options=[item.letter for item in selection.proposals],
        recommended=selection.recommended,
        reasons=selection.reasons,
    )


def record_concept_decision(
    crew: Crew, state: ProjectState, gate: ConceptGate, decision: Decision
) -> ProjectUpdate:
    """The client's decision, recorded once per version of the presentation, and where the work goes next."""
    project = state["project"]
    (file,) = gate.files
    digest = {file: sha256_under(crew.work_dir(project), file)}
    approved, choice = concept_choice(decision, gate.options)
    recorded = {entry.files_json for entry in crew.ledger.gates(project) if entry.gate == "concept"}
    if json.dumps(digest) not in recorded:
        crew.ledger.add_gate(
            GateEntry(
                at=now(),
                project=project,
                gate="concept",
                approved=approved,
                choice=choice,
                text=decision.text,
                files_json=json.dumps(digest),
            )
        )
    if approved:
        return {"route": "start_production", "chosen": choice, "client_note": decision.text}
    return {"route": "plan", "client_note": f"Il cliente chiede: {decision.text}"}
