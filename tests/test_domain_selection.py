"""The selection's pure rules (ADR-0058): no ledger, no files, no framework."""

from __future__ import annotations

from agency.contracts.concept import ConceptCard
from agency.contracts.ticket import TicketSpec, TicketType
from agency.studio.selection.domain import (
    MAX_DEVELOPED,
    board_review_spec,
    concept_sheets,
    first_look_refusal,
    rating_refusal,
    selection_note,
    selection_refusal,
)

CARD = ConceptCard(
    concept="Il merlo che fischia il turno",
    client_fact="L'officina apre con un fischio",
    why_not_obvious="Evita la chiave inglese",
    drawing="Un merlo stilizzato",
    substitution="Un'altra officina non ha quel fischio",
)


def test_rating_refusal_asks_for_every_letter_on_the_board_and_only_those() -> None:
    assert rating_refusal({"A"}, {"A", "B"}) == "valuta tutte e sole le lettere della tavola: ['A', 'B']"
    assert (
        rating_refusal({"A", "B", "C"}, {"A", "B"})
        == "valuta tutte e sole le lettere della tavola: ['A', 'B']"
    )
    assert rating_refusal({"A", "B"}, {"A", "B"}) is None


def test_selection_refusal_names_the_letters_that_are_not_on_the_board() -> None:
    assert selection_refusal(["Z", "A"], {"A", "B"}) == "lettere inesistenti: ['Z']. Disponibili: ['A', 'B']"


def test_selection_refusal_keeps_at_most_three_ideas() -> None:
    assert MAX_DEVELOPED == 3
    four = ["A", "B", "C", "D"]
    assert selection_refusal(four, set(four)) == (
        "si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto"
    )


def test_selection_refusal_accepts_up_to_three_ideas_or_none() -> None:
    assert selection_refusal(["A", "B", "C"], {"A", "B", "C", "D"}) is None
    assert selection_refusal([], {"A"}) is None


def test_first_look_refusal_names_the_ideas_that_did_not_pass() -> None:
    assert first_look_refusal(["C", "A", "B"], {"A"}) == (
        "['B', 'C'] non hanno passato il primo sguardo: un segno che ha bisogno di spiegazioni non va "
        "avanti. "
        "Scegli tra quelli che passano, o passa chosen vuoto per esplorare di nuovo."
    )
    assert first_look_refusal(["A"], {"A", "B"}) is None


def test_board_review_spec_asks_the_critic_to_judge_the_board() -> None:
    assert board_review_spec(2, "T-0001") == TicketSpec(
        title="Tavola delle idee r2",
        request="Giudica le idee sulla tavola, rispetto a brief.md.",
        type=TicketType.REVIEW,
        sender="design-director",
        assignee="critic",
        outputs=["tavola.png", "reviews/selezione.md", "reviews/valutazione.json"],
        checks={"tavola.png": ["board_review"]},
        exempt={"reviews/valutazione.json": "il primo sguardo lo registra rate_board"},
        parent="T-0001",
        workspace="board/r2",
        prompt="critic-board",
    )


def test_concept_sheets_list_each_idea_under_its_anonymous_letter() -> None:
    assert concept_sheets([("A", CARD)]) == (
        "# Schede delle idee\n\n## A\nIl merlo che fischia il turno\n"
        "Fatto: L'officina apre con un fischio\n\n"
        "Non ovvia: Evita la chiave inglese\nSostituzione: Un'altra officina non ha quel fischio\n"
    )


def test_selection_note_points_the_director_at_everything_on_the_board() -> None:
    assert selection_note("board/r1") == (
        "Tavola: board/r1/tavola.png. Primo sguardo: board/r1/reviews/valutazione.json. "
        "Critica: board/r1/reviews/selezione.md. Schede: board/r1/schede.md. "
        "Tutte le miniature di ogni idea: board/r1/fogli/<lettera>.png."
    )
