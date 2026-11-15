"""The presentation's pure rules (ADR-0058): no ledger, no files, no framework."""

from __future__ import annotations

from agency.contracts.concept import ConceptCard
from agency.contracts.gate import Decision
from agency.studio.presentation.domain import concept_choice, draft_refusal, proposals_digest

CARD = ConceptCard(
    concept="Il merlo che fischia il turno",
    client_fact="L'officina apre con un fischio",
    why_not_obvious="Evita la chiave inglese",
    drawing="Un merlo stilizzato",
    substitution="Un'altra officina non ha quel fischio",
)


def test_draft_refusal_names_the_proposals_that_were_not_developed() -> None:
    assert (
        draft_refusal(["Z", "A"], {"A", "B"}, "A") == "proposte inesistenti: ['Z']. Disponibili: ['A', 'B']"
    )


def test_draft_refusal_wants_the_recommendation_among_the_proposals_presented() -> None:
    assert draft_refusal(["A"], {"A", "B"}, "B") == "lo studio raccomanda una delle proposte che presenta"
    assert draft_refusal(["A"], {"A", "B"}, None) == "lo studio raccomanda una delle proposte che presenta"


def test_draft_refusal_accepts_a_valid_draft_and_an_empty_one() -> None:
    assert draft_refusal(["A", "B"], {"A", "B"}, "B") is None
    assert draft_refusal([], {"A"}, None) is None  # no proposal holds up: the tool closes the phase instead


def test_proposals_digest_shows_each_proposal_with_the_view_to_look_at() -> None:
    assert proposals_digest([("A", "proposals/r1/insieme-a.png", CARD)]) == (
        "# Proposte sviluppate\n\n## A\nDa guardare: proposals/r1/insieme-a.png\n"
        "Il merlo che fischia il turno\nFatto: L'officina apre con un fischio\n"
    )


def test_concept_choice_approves_only_a_presented_option() -> None:
    assert concept_choice(Decision(approved=True, text="Va bene", choice="B"), ["A", "B"]) == (True, "B")
    assert concept_choice(Decision(approved=True, text="Va bene", choice="Z"), ["A", "B"]) == (False, "Z")
    assert concept_choice(Decision(approved=False, text="Ancora", choice="B"), ["A", "B"]) == (False, "B")
