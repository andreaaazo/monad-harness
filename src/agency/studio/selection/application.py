"""The selection's use cases, without LangGraph: the nodes are thin adapters over them (ADR-0058)."""

from __future__ import annotations

from agency.contracts.concept import ConceptCard
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE, Action, Status
from agency.studio.selection.domain import board_review_spec, concept_sheets, selection_note
from agency.studio.selection.tools import SelectConcepts
from agency.studio.shared import END_ROUTE, Crew, ProjectState, ProjectUpdate, copy_capped
from agency.workshop import board
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    replace_under,
)


def build_board(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The anonymous board of the round's delivered sketches, with the brief beside it."""
    project, turn = state["project"], state["exploration"]
    done = (Status.DELIVERED, Status.ACCEPTED)
    rows = [
        row for row in crew.ledger.concepts(project, turn) if crew.ledger.status(row.idea_ticket)[0] in done
    ]
    if not rows:
        return {"outcome": "bloccato: nessuna esplorazione consegnata"}
    anon = board.assign_letters(project, turn, [row.letter for row in rows])
    work = crew.work_dir(project)
    items = []
    for row in rows:
        file = f"explorations/r{turn}/{row.letter}/schizzo-{row.letter}.png"
        crew.ledger.update_concept(row.idea_ticket, anon=anon[row.letter], sketch_file=file)
        items.append((anon[row.letter], work / file))
        if crew.ledger.status(row.idea_ticket)[0] is Status.DELIVERED:
            crew.ledger.apply(row.idea_ticket, Action.ACCEPT, "design-director", "passa alla tavola")
    folder = f"board/r{turn}"
    board.build(items, work / folder / "tavola.png")
    copy_capped(work, "brief.md", f"{folder}/brief.md", MAX_TEXT_FILE_BYTES)
    return {}


def review_board(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The critic's first look at the board: its ticket is opened once per round, and runs while it has
    work."""
    project, turn = state["project"], state["exploration"]
    spec = board_review_spec(turn, state["root"])
    existing = [
        ticket
        for ticket in crew.ledger.children(state["root"])
        if crew.ledger.spec(ticket).title == spec.title
    ]
    ticket = existing[0] if existing else crew.ledger.open(spec, project)
    if crew.ledger.status(ticket)[0] in RUNNABLE:
        crew.runner.run(ticket, exploration=turn)
    return {}


def choose_concepts(crew: Crew, state: ProjectState) -> ProjectUpdate:
    """The choice among the sketches is the studio's: the client never sees them."""
    project, turn = state["project"], state["exploration"]
    work = crew.work_dir(project)
    rows = [row for row in crew.ledger.concepts(project, turn) if row.anon]
    cards = [(row.anon, ConceptCard.model_validate_json(row.card_json)) for row in rows]
    folder = f"board/r{turn}"
    replace_under(work, f"{folder}/schede.md", concept_sheets(cards).encode("utf-8"))
    ensure_dir_under(work, f"{folder}/fogli")
    for row in rows:
        try:  # a missing sheet is skipped; a link is refused, not followed
            sheet = read_under(
                work, f"explorations/r{turn}/{row.letter}/foglio-{row.letter}.png", MAX_IMAGE_FILE_BYTES
            )
        except FileNotFoundError:
            continue
        replace_under(work, f"{folder}/fogli/{row.anon}.png", sheet)
    outcome = crew.runner.run(state["root"], turn, selection_note(folder), mode="select")
    for ticket in crew.ledger.children(state["root"]):
        spec = crew.ledger.spec(ticket)
        if spec.prompt == "critic-board" and crew.ledger.status(ticket)[0] is Status.DELIVERED:
            crew.ledger.apply(ticket, Action.ACCEPT, spec.sender, "referto letto")
    if outcome.state is OutcomeState.SELECTED:
        return {"route": "prepare_proposals", "client_note": ""}
    if outcome.state is OutcomeState.NO_CONCEPT:
        reasons = SelectConcepts.model_validate_json(outcome.note).reasons
        return {"route": "plan", "client_note": f"Le idee precedenti non reggono: {reasons}"}
    return {"route": END_ROUTE, "outcome": f"bloccato: {outcome.note[:300]}"}
