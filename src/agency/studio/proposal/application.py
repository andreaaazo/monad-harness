"""The proposal's use cases, without LangGraph: the nodes and the router are thin adapters over them
(ADR-0058)."""

from __future__ import annotations

import json

from agency.contracts.concept import ConceptStatus
from agency.contracts.ticket import RUNNABLE
from agency.studio.proposal.domain import proposal_spec
from agency.studio.shared import (
    Crew,
    ProjectState,
    ProjectUpdate,
    Route,
    attempt,
    copy_capped,
    proposal_tickets,
    proposal_title,
)
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    sha256_under,
)


def open_proposals(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """One proposal ticket per chosen idea, with the brief, the card and the sketch copied beside it."""
    project, turn, root = state["project"], state["exploration"], state["root"]
    work = crew.work_dir(project)
    existing = {crew.ledger.spec(ticket).title for ticket in proposal_tickets(crew, state)}
    applications = json.loads(
        read_under(work, f"explorations/r{turn}/applicazioni.json", MAX_TEXT_FILE_BYTES).decode("utf-8")
    )
    chosen = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.SELECTED]
    for row in sorted(chosen, key=lambda item: item.anon):
        title = proposal_title(row.anon, turn)
        if title in existing:  # a replay: the ticket was opened, the status may not have been set
            crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
            continue
        spec = proposal_spec(
            title=title,
            anon=row.anon,
            turn=turn,
            card_json=row.card_json,
            applications=applications,
            root=root,
            effort=crew.settings.proposal_effort,
        )
        workspace = spec.workspace
        ensure_dir_under(work, workspace)
        source = f"explorations/r{turn}/{row.letter}"
        copy_capped(work, "brief.md", f"{workspace}/brief.md", MAX_TEXT_FILE_BYTES)
        copy_capped(work, f"{source}/scheda.json", f"{workspace}/scheda.json", MAX_TEXT_FILE_BYTES)
        copy_capped(work, row.sketch_file, f"{workspace}/schizzo.png", MAX_IMAGE_FILE_BYTES)
        hashes = {path: sha256_under(work, f"{workspace}/{path}") for path in spec.inputs}
        crew.ledger.open(spec, project, hashes)
        crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
    return {}


def proposals_to_run(crew: Crew, state: ProjectState) -> list[str] | Route:
    """The proposal tickets of this round that still have work to do, or the presentation without them."""
    tickets = [
        ticket for ticket in proposal_tickets(crew, state) if crew.ledger.status(ticket)[0] in RUNNABLE
    ]
    return tickets or "present"


def develop(crew: Crew, ticket: str) -> None:
    """One designer develops its proposal, as a new attempt after each rework."""
    crew.runner.run(ticket, attempt(crew.ledger, ticket))
