"""The delivery's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

SHOWN_PROBLEMS = 12  # what the director reads back after a refused acceptance


def acceptance_refusal(problems: list[str]) -> str:
    """What the director reads when the system refuses an acceptance the client gave: the first problems."""
    return "Accettazione rifiutata dal sistema:\n" + "\n".join(problems[:SHOWN_PROBLEMS])
