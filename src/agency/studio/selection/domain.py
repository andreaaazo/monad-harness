"""The selection's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

from agency.contracts.concept import ConceptCard
from agency.contracts.ticket import TicketSpec, TicketType

MAX_DEVELOPED = 3  # choosing more ideas than this means not having chosen


def rating_refusal(rated: set[str], letters: set[str]) -> str | None:
    """Why a first look cannot be recorded: it must rate every letter on the board, and only those."""
    if rated != letters:
        return f"valuta tutte e sole le lettere della tavola: {sorted(letters)}"
    return None


def selection_refusal(chosen: list[str], available: set[str]) -> str | None:
    """Why a choice cannot stand: a letter that is not on the board, or more ideas than the studio
    develops."""
    unknown = sorted(set(chosen) - available)
    if unknown:
        return f"lettere inesistenti: {unknown}. Disponibili: {sorted(available)}"
    if len(chosen) > MAX_DEVELOPED:
        return "si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto"
    return None


def first_look_refusal(chosen: list[str], passed: set[str]) -> str | None:
    """Why a choice cannot stand: an idea that did not pass the critic's first look."""
    failed = sorted(set(chosen) - passed)
    if failed:
        return (
            f"{failed} non hanno passato il primo sguardo: un segno che ha bisogno di spiegazioni non va "
            "avanti. Scegli tra quelli che passano, o passa chosen vuoto per esplorare di nuovo."
        )
    return None


def board_review_spec(turn: int, root: str) -> TicketSpec:
    """The critic's ticket on the anonymous board of round `turn`."""
    return TicketSpec(
        title=f"Tavola delle idee r{turn}",
        request="Giudica le idee sulla tavola, rispetto a brief.md.",
        type=TicketType.REVIEW,
        sender="design-director",
        assignee="critic",
        outputs=["tavola.png", "reviews/selezione.md", "reviews/valutazione.json"],
        checks={"tavola.png": ["board_review"]},
        exempt={"reviews/valutazione.json": "il primo sguardo lo registra rate_board"},
        parent=root,
        workspace=f"board/r{turn}",
        prompt="critic-board",
    )


def concept_sheets(cards: list[tuple[str, ConceptCard]]) -> str:
    """The ideas' cards for the director, each under its anonymous letter."""
    lines = ["# Schede delle idee", ""]
    for anon, card in cards:
        lines += [f"## {anon}", card.concept, f"Fatto: {card.client_fact}", ""]
        lines += [f"Non ovvia: {card.why_not_obvious}", f"Sostituzione: {card.substitution}", ""]
    return "\n".join(lines)


def selection_note(folder: str) -> str:
    """What the director reads when it chooses: where the board, the first look, the critique, the cards
    and the sheets are."""
    return (
        f"Tavola: {folder}/tavola.png. Primo sguardo: {folder}/reviews/valutazione.json. "
        f"Critica: {folder}/reviews/selezione.md. Schede: {folder}/schede.md. "
        f"Tutte le miniature di ogni idea: {folder}/fogli/<lettera>.png."
    )
