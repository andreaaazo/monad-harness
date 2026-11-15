"""The presentation nodes: the director presents the proposals, and the client chooses at the
`concept` gate."""

from __future__ import annotations

import json

from langgraph.types import interrupt

from agency.contracts.concept import ConceptCard, ConceptStatus
from agency.contracts.gate import ConceptGate, Decision
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import Action, Status
from agency.ledger.models import GateRow
from agency.ledger.store import now
from agency.studio.graph import Node
from agency.studio.presentation import document as presentation
from agency.studio.presentation.tools import PresentConcepts
from agency.studio.shared import END_ROUTE, Crew, ProjectState, ProjectUpdate, proposal_tickets
from agency.workshop.files import sha256_under


def present(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        project, turn, root = state["project"], state["exploration"], state["root"]
        concepts = {
            f"Proposta {row.anon} r{turn}": row for row in crew.ledger.concepts(project, turn) if row.anon
        }
        lines = ["# Proposte sviluppate", ""]
        for ticket in proposal_tickets(crew, state):
            status, _ = crew.ledger.status(ticket)
            title = crew.ledger.spec(ticket).title
            if status is Status.DELIVERED:
                crew.ledger.apply(ticket, Action.ACCEPT, "design-director", "pronta per la presentazione")
            if crew.ledger.status(ticket)[0] is not Status.ACCEPTED:
                continue
            row = concepts[title]
            crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.PROPOSAL)
            mark, applications = presentation.proposal_files(
                crew.work_dir(project), turn, row.anon, crew.ledger.delivered(ticket)
            )
            view = f"proposals/r{turn}/insieme-{row.anon.lower()}.png"
            presentation.sheet(mark, applications, crew.work_dir(project) / view)
            card = ConceptCard.model_validate_json(row.card_json)
            lines += [
                f"## {row.anon}",
                f"Da guardare: {view}",
                card.concept,
                f"Fatto: {card.client_fact}",
                "",
            ]
        ready = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.PROPOSAL]
        if not ready:
            return {"route": END_ROUTE, "outcome": "bloccato: nessuna proposta è stata sviluppata"}
        outcome = crew.runner.run(root, turn, "\n".join(lines), mode="present")
        if outcome.state is OutcomeState.PRESENTED:  # the PDF exists, and the director viewed every page
            return {"route": "concept_gate", "client_note": outcome.note}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = PresentConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le proposte non reggono: {reasons}"}
        return {"route": END_ROUTE, "outcome": f"bloccato: {outcome.note[:300]}"}

    return node


def concept_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> ProjectUpdate:
        project, turn = state["project"], state["exploration"]
        selection = PresentConcepts.model_validate_json(state["client_note"])
        if selection.recommended is None:  # draft_presentation refuses a draft without a recommendation
            raise ValueError("a presentation without a recommendation never reaches the gate")
        options = [item.letter for item in selection.proposals]
        file = presentation.pdf_of(turn)
        gate = ConceptGate(
            ticket=state["root"],
            files=[file],
            options=options,
            recommended=selection.recommended,
            reasons=selection.reasons,
        )
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        digest = {file: sha256_under(crew.work_dir(project), file)}
        choice = decision.choice
        approved = decision.approved and choice in options
        recorded = {gate.files_json for gate in crew.ledger.gates(project) if gate.gate == "concept"}
        if json.dumps(digest) not in recorded:
            crew.ledger.add_gate(
                GateRow(
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

    return node
