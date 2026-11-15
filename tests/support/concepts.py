"""Concept rows written as the studio writes them: each with its idea ticket, in one transaction."""

from __future__ import annotations

from agency.contracts.ledger import ConceptEntry
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger


def open_idea(ledger: Ledger, row: ConceptEntry) -> str:
    """Opens the sketch ticket of `row`'s letter together with the row, as `plan_exploration` does, and
    returns the ticket. The concept row the ledger writes takes that ticket's id as its `idea_ticket`."""
    letter = row.letter
    spec = TicketSpec(
        title=f"Esplorazione {letter.upper()}",
        request="Uno schizzo per la leva",
        type=TicketType.SKETCH,
        sender="design-director",
        assignee=f"direction-{letter}",
        outputs=[
            "scheda.json",
            f"schizzi-{letter}.vectorcraft",
            f"foglio-{letter}.png",
            f"schizzo-{letter}.png",
        ],
        checks={"*.vectorcraft": ["master_open"], "*.png": ["visual_review"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.VECTOR],
        prompt="explorer",
    )
    return ledger.open(spec, row.project, concept=row)
