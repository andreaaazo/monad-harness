"""The delivery's pure rules (ADR-0058): no ledger, no files, no framework."""

from __future__ import annotations

from agency.studio.delivery.domain import acceptance_refusal


def test_acceptance_refusal_names_the_problem() -> None:
    assert acceptance_refusal(["segno.svg: 'svg_audit' manca"]) == (
        "Accettazione rifiutata dal sistema:\nsegno.svg: 'svg_audit' manca"
    )


def test_acceptance_refusal_lists_only_the_first_twelve_problems() -> None:
    problems = [f"file-{number}.png: modificato dopo la consegna" for number in range(15)]
    refusal = acceptance_refusal(problems)
    assert refusal.splitlines() == ["Accettazione rifiutata dal sistema:", *problems[:12]]
