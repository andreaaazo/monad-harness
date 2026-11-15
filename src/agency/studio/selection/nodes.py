"""The selection nodes: the anonymous board, the critic's first look and the director's choice."""

from __future__ import annotations

from langgraph.graph import END

from agency.contracts.concept import ConceptCard
from agency.contracts.outcome import OutcomeState
from agency.contracts.ticket import RUNNABLE, Action, Status, TicketSpec, TicketType
from agency.studio.selection.tools import SelectConcepts
from agency.studio.shared import Crew, Node, ProjectState, copy_capped
from agency.workshop import board
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    replace_under,
)


def make_board(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        done = (Status.DELIVERED, Status.ACCEPTED)
        rows = [
            row
            for row in crew.ledger.concepts(project, turn)
            if crew.ledger.status(row.idea_ticket)[0] in done
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

    return node


def board_review(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        children = crew.ledger.children(state["root"])
        title = f"Tavola delle idee r{turn}"
        existing = [ticket for ticket in children if crew.ledger.spec(ticket).title == title]
        if existing:
            ticket = existing[0]
        else:
            spec = TicketSpec(
                title=title,
                request="Giudica le idee sulla tavola, rispetto a brief.md.",
                type=TicketType.REVIEW,
                sender="design-director",
                assignee="critic",
                outputs=["tavola.png", "reviews/selezione.md", "reviews/valutazione.json"],
                checks={"tavola.png": ["board_review"]},
                exempt={"reviews/valutazione.json": "il primo sguardo lo registra rate_board"},
                parent=state["root"],
                workspace=f"board/r{turn}",
                prompt="critic-board",
            )
            ticket = crew.ledger.open(spec, project)
        if crew.ledger.status(ticket)[0] in RUNNABLE:
            crew.runner.run(ticket, exploration=turn)
        return {}

    return node


def select(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        """The choice among the sketches is the studio's: the client never sees them."""
        project, turn = state["project"], state["exploration"]
        work = crew.work_dir(project)
        lines = ["# Schede delle idee", ""]
        for row in crew.ledger.concepts(project, turn):
            if row.anon:
                card = ConceptCard.model_validate_json(row.card_json)
                lines += [f"## {row.anon}", card.concept, f"Fatto: {card.client_fact}", ""]
                lines += [f"Non ovvia: {card.why_not_obvious}", f"Sostituzione: {card.substitution}", ""]
        folder = f"board/r{turn}"
        replace_under(work, f"{folder}/schede.md", "\n".join(lines).encode("utf-8"))
        ensure_dir_under(work, f"{folder}/fogli")
        for row in crew.ledger.concepts(project, turn):
            if not row.anon:
                continue
            try:  # a missing sheet is skipped; a link is refused, not followed
                sheet = read_under(
                    work, f"explorations/r{turn}/{row.letter}/foglio-{row.letter}.png", MAX_IMAGE_FILE_BYTES
                )
            except FileNotFoundError:
                continue
            replace_under(work, f"{folder}/fogli/{row.anon}.png", sheet)
        note = (
            f"Tavola: {folder}/tavola.png. Primo sguardo: {folder}/reviews/valutazione.json. "
            f"Critica: {folder}/reviews/selezione.md. Schede: {folder}/schede.md. "
            f"Tutte le miniature di ogni idea: {folder}/fogli/<lettera>.png."
        )
        outcome = crew.runner.run(state["root"], turn, note, mode="select")
        for ticket in crew.ledger.children(state["root"]):
            spec = crew.ledger.spec(ticket)
            if spec.prompt == "critic-board" and crew.ledger.status(ticket)[0] is Status.DELIVERED:
                crew.ledger.apply(ticket, Action.ACCEPT, spec.sender, "referto letto")
        if outcome.state is OutcomeState.SELECTED:
            return {"route": "prepare_proposals", "client_note": ""}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = SelectConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le idee precedenti non reggono: {reasons}"}
        return {"route": END, "outcome": f"bloccato: {outcome.note[:300]}"}

    return node
