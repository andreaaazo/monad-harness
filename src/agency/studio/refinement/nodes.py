"""The refinement nodes: the finisher starts from the chosen proposal, the director leads the
revisions and the team works them."""

from __future__ import annotations

from pathlib import PurePosixPath

from agency.contracts.concept import ConceptStatus
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE, Medium, TicketSpec, TicketType
from agency.studio.shared import Crew, Node, ProjectState, attempt, copy_capped, rework_note
from agency.workshop.files import MAX_DOCUMENT_BYTES, ensure_dir_under, sha256_under


def start_production(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        """The finisher starts from the approved proposal: its master is already the one the client chose."""
        project, turn, root = state["project"], state["exploration"], state["root"]
        spec = crew.ledger.spec(root)
        row = next(item for item in crew.ledger.concepts(project, turn) if item.anon == state["chosen"])
        crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.CHOSEN)
        title = f"Rifinitura {row.anon} r{turn}"  # per round: a rejected concept makes way for the new one
        if any(crew.ledger.spec(ticket).title == title for ticket in crew.ledger.children(root)):
            return {"client_note": ""}
        letter = row.anon.lower()
        folder = f"proposals/r{turn}/{letter}"
        work = crew.work_dir(project)
        target = next(path for path in spec.outputs if path.endswith(".vectorcraft"))
        if PurePosixPath(target).parent.parts:
            ensure_dir_under(work, str(PurePosixPath(target).parent))
        copy_capped(work, f"{folder}/proposta-{letter}.vectorcraft", target, MAX_DOCUMENT_BYTES)
        production = TicketSpec(
            title=title,
            request=f"{spec.request}\n\nCONCETTO SCELTO DAL CLIENTE\n{row.card_json}\n\n"
            f"Il cliente ha detto: {state['client_note']}",
            type=TicketType.PRODUCTION,
            sender="design-director",
            assignee="identity-designer",
            outputs=spec.outputs,
            checks={
                pattern: [name for name in names if name != "critique"]
                for pattern, names in spec.checks.items()
            },
            exempt=spec.exempt,
            media=[Medium.VECTOR],
            inputs=[f"{folder}/scheda.json", f"{folder}/proposta-{letter}.png"],
            parent=root,
            prompt="finisher",
        )
        hashes = {path: sha256_under(work, path) for path in production.inputs}
        crew.ledger.open(production, project, hashes)
        return {"client_note": ""}

    return node


def lead(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        root, turn = state["root"], state["round"] + 1
        status, _ = crew.ledger.status(root)
        if status in RUNNABLE:
            # Each of the director's turns is a new instance: nobody sits waiting.
            outcome = crew.runner.run(root, turn, state["client_note"])
            if outcome.state is OutcomeState.BLOCKED:
                return {"round": turn, "outcome": f"bloccato: {outcome.note}"}
            if outcome.state is OutcomeState.CONCEPT_REJECTED:
                return {
                    "round": turn,
                    "route": "rejected",
                    "client_note": f"Concetto bocciato: {outcome.note}",
                }
        return {"round": turn, "client_note": "", "route": ""}

    return node


def team(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        for ticket in crew.ledger.children(state["root"]):
            status, _ = crew.ledger.status(ticket)
            if status in RUNNABLE:
                crew.runner.run(ticket, attempt(crew.ledger, ticket), rework_note(crew.ledger, ticket))
        return {}

    return node
