"""The refinement's pure rules (ADR-0058): no ledger, no files, no framework."""

from __future__ import annotations

from agency.contracts.registry import RoleSpec, StudioRules
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.studio.refinement.domain import (
    opening_refusal,
    production_spec,
    production_title,
    rejection_refusal,
    rework_refusal,
)

RULES = StudioRules(
    roles={
        "design-director": RoleSpec(tools="director", model="claude-opus-5-5", effort="high", craft=[]),
        "identity-designer": RoleSpec(tools="author", model="claude-opus-5-5", effort="high", craft=[]),
        "copywriter": RoleSpec(tools="author", model="claude-opus-5-5", effort="high", craft=[]),
    },
    org={"design-director": ["identity-designer", "copywriter", "ghost"]},
    checks={},
    active=frozenset({"design-director", "identity-designer"}),
)


def test_opening_refusal_when_the_org_chart_does_not_allow_the_sender() -> None:
    assert opening_refusal(RULES, "identity-designer", "copywriter") == (
        "identity-designer non può aprire ticket verso copywriter"
    )


def test_opening_refusal_for_a_role_that_does_not_exist() -> None:
    assert opening_refusal(RULES, "design-director", "ghost") == "ruolo inesistente: ghost"


def test_opening_refusal_for_a_role_without_a_prompt() -> None:
    assert opening_refusal(RULES, "design-director", "copywriter") == (
        "copywriter non è ancora attivo nello studio: affida il lavoro a un altro ruolo"
    )


def test_opening_refusal_lets_an_allowed_active_role_through() -> None:
    assert opening_refusal(RULES, "design-director", "identity-designer") is None


def test_rework_refusal_wants_a_note_that_says_what_to_change() -> None:
    assert rework_refusal("   breve   ") == "scrivi cosa va cambiato"
    assert rework_refusal("più spazio") is None  # ten characters are enough


def test_rejection_refusal_wants_a_reason_with_evidence() -> None:
    assert rejection_refusal("non regge proprio") == (
        "spiega con una prova perché il concetto, e non l'esecuzione, non regge"
    )
    assert rejection_refusal("il merlo si confonde") is None  # twenty characters are enough


def test_a_production_ticket_is_titled_by_its_letter_and_round() -> None:
    assert production_title("B", 2) == "Rifinitura B r2"


def test_production_spec_starts_the_finisher_from_the_chosen_proposal() -> None:
    root = TicketSpec(
        title="Logo",
        request="Un segno per l'officina",
        type=TicketType.DELIVERY,
        sender="router",
        assignee="design-director",
        outputs=["source/segno.vectorcraft", "exports/segno.svg"],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]},
        exempt={"construction.md": "documento di costruzione"},
    )
    spec = production_spec(
        root=root,
        title="Rifinitura B r2",
        card_json='{"concept": "Il merlo"}',
        client_note="Più spesso",
        folder="proposals/r2/b",
        letter="b",
        parent="T-0001",
    )
    assert spec == TicketSpec(
        title="Rifinitura B r2",
        request='Un segno per l\'officina\n\nCONCETTO SCELTO DAL CLIENTE\n{"concept": "Il merlo"}\n\n'
        "Il cliente ha detto: Più spesso",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=["source/segno.vectorcraft", "exports/segno.svg"],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"]},
        exempt={"construction.md": "documento di costruzione"},
        media=[Medium.VECTOR],
        inputs=["proposals/r2/b/scheda.json", "proposals/r2/b/proposta-b.png"],
        parent="T-0001",
        prompt="finisher",
    )
