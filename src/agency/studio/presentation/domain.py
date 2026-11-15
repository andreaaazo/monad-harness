"""The presentation's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

from agency.contracts.concept import ConceptCard
from agency.contracts.gate import Decision


def draft_refusal(letters: list[str], available: set[str], recommended: str | None) -> str | None:
    """Why a draft cannot be built: a proposal that was not developed, or a recommendation the draft does not
    present. An empty draft is not refused: it says that no proposal holds up."""
    unknown = sorted(set(letters) - available)
    if unknown:
        return f"proposte inesistenti: {unknown}. Disponibili: {sorted(available)}"
    if letters and recommended not in letters:
        return "lo studio raccomanda una delle proposte che presenta"
    return None


def proposals_digest(items: list[tuple[str, str, ConceptCard]]) -> str:
    """What the director reads before drafting: each proposal's letter, the view to look at, and its idea."""
    lines = ["# Proposte sviluppate", ""]
    for anon, view, card in items:
        lines += [f"## {anon}", f"Da guardare: {view}", card.concept, f"Fatto: {card.client_fact}", ""]
    return "\n".join(lines)


def concept_choice(decision: Decision, options: list[str]) -> tuple[bool, str]:
    """Whether the client approved one of the options presented, and which letter they named."""
    return decision.approved and decision.choice in options, decision.choice
