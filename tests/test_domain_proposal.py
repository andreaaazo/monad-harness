"""The proposal's pure rules (ADR-0058), and the proposal title the presentation also reads."""

from __future__ import annotations

from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.studio.proposal.domain import proposal_spec
from agency.studio.shared import proposal_title

CARD_JSON = '{"concept": "Il merlo che fischia il turno"}'
APPLICATIONS = [
    {"name": "insegna", "size": "120 cm di larghezza"},
    {"name": "timbro", "size": "16 mm di larghezza"},
]


def test_a_proposal_ticket_is_titled_by_its_letter_and_round() -> None:
    assert proposal_title("B", 2) == "Proposta B r2"


def test_proposal_spec_asks_the_designer_for_the_mark_and_its_applications() -> None:
    spec = proposal_spec(
        title="Proposta B r2",
        anon="B",
        turn=2,
        card_json=CARD_JSON,
        applications=APPLICATIONS,
        root="T-0001",
        effort="high",
    )
    assert spec == TicketSpec(
        title="Proposta B r2",
        request="Sviluppa questa idea in una proposta.\n\n"
        '{"concept": "Il merlo che fischia il turno"}\n\n'
        "APPLICAZIONI\n- insegna: 120 cm di larghezza\n- timbro: 16 mm di larghezza",
        type=TicketType.PROPOSAL,
        sender="design-director",
        assignee="identity-designer",
        outputs=["proposta-b.vectorcraft", "proposta-b.svg", "proposta-b.png", "applicazioni-b/*.png"],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"], "*.png": ["visual_review"]},
        media=[Medium.VECTOR],
        inputs=["scheda.json", "schizzo.png"],
        parent="T-0001",
        workspace="proposals/r2/b",
        prompt="proposer",
        effort="high",
    )
