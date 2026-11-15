"""The refinement's use cases, without LangGraph: the nodes are thin adapters over them (ADR-0058)."""

from __future__ import annotations

from pathlib import PurePosixPath

from agency.contracts.concept import ConceptStatus
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE
from agency.studio.refinement.domain import production_spec, production_title
from agency.studio.shared import Crew, ProjectState, ProjectUpdate, attempt, copy_capped, rework_note
from agency.workshop.files import MAX_DOCUMENT_BYTES, ensure_dir_under, sha256_under


def open_production(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The finisher starts from the approved proposal: its master is already the one the client chose."""
    project, turn, root = state["project"], state["exploration"], state["root"]
    spec = crew.ledger.spec(root)
    row = next(item for item in crew.ledger.concepts(project, turn) if item.anon == state["chosen"])
    crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.CHOSEN)
    title = production_title(row.anon, turn)
    if any(crew.ledger.spec(ticket).title == title for ticket in crew.ledger.children(root)):
        return {"client_note": ""}
    letter = row.anon.lower()
    folder = f"proposals/r{turn}/{letter}"
    work = crew.work_dir(project)
    target = next(path for path in spec.outputs if path.endswith(".vectorcraft"))
    if PurePosixPath(target).parent.parts:
        ensure_dir_under(work, str(PurePosixPath(target).parent))
    copy_capped(work, f"{folder}/proposta-{letter}.vectorcraft", target, MAX_DOCUMENT_BYTES)
    production = production_spec(
        root=spec,
        title=title,
        card_json=row.card_json,
        client_note=state["client_note"],
        folder=folder,
        letter=letter,
        parent=root,
    )
    hashes = {path: sha256_under(work, path) for path in production.inputs}
    crew.ledger.open(production, project, hashes)
    return {"client_note": ""}


def direct(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """One turn of the director on the client's ticket: each turn is a new instance, nobody sits waiting."""
    root, turn = state["root"], state["round"] + 1
    status, _ = crew.ledger.status(root)
    if status in RUNNABLE:
        outcome = crew.runner.run(root, turn, state["client_note"])
        if outcome.state is OutcomeState.BLOCKED:
            return {"round": turn, "outcome": f"bloccato: {outcome.note}"}
        if outcome.state is OutcomeState.CONCEPT_REJECTED:
            return {"round": turn, "route": "rejected", "client_note": f"Concetto bocciato: {outcome.note}"}
    return {"round": turn, "client_note": "", "route": ""}


def run_team(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """Every child ticket with work to do runs, as a new attempt with its rework note after each rework."""
    for ticket in crew.ledger.children(state["root"]):
        status, _ = crew.ledger.status(ticket)
        if status in RUNNABLE:
            crew.runner.run(ticket, attempt(crew.ledger, ticket), rework_note(crew.ledger, ticket))
    return {}
