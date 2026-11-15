"""Builds each role's stable system prompt and the ticket packet an instance starts from."""

from __future__ import annotations

import json

from agency.contracts.ledger import Tickets
from agency.registry import PROMPTS, skills_index


def system_prompt(name: str) -> str:
    """Identical across the instances of a role: no dates or ids, or the prompt cache misses."""
    common = (PROMPTS / "common.md").read_text(encoding="utf-8")
    body = (PROMPTS / "roles" / f"{name}.md").read_text(encoding="utf-8")
    return (
        f"{common}\n{body}\nSkill disponibili con read_skill: {skills_index()}; org: craft.md, "
        "anti-patterns.md, lessons.md, review.md."
    )


def packet(ledger: Tickets, ticket_id: str, rework_note: str = "") -> str:
    """An instance's first message: the ticket's contract, the note of this turn, and its children's state."""
    spec = ledger.spec(ticket_id)
    lines = [
        "Scrivi note, referti e documenti in italiano.",
        f"TICKET {ticket_id} · tipo {spec.type.value} · da {spec.sender}",
        f"TITOLO {spec.title}",
        "",
        "RICHIESTA",
        spec.request,
        "",
        f"MEZZO {', '.join(m.value for m in spec.media) or '-'}",
        f"INPUT {', '.join(spec.inputs) or '-'}",
        f"OUTPUT {', '.join(spec.outputs) or '-'}",
        f"CONTROLLI {json.dumps(spec.checks, ensure_ascii=False)}",
    ]
    if spec.exempt:
        lines.append(f"ESENTI {json.dumps(spec.exempt, ensure_ascii=False)}")
    if spec.acceptance:
        lines.append(f"ACCETTAZIONE {spec.acceptance}")
    if rework_note:
        lines += ["", "NOTE PER QUESTO TURNO", rework_note]
    children = ledger.children(ticket_id)
    if children:
        lines += ["", "TICKET FIGLI"] + [_child_line(ledger, child) for child in children]
    return "\n".join(lines)


def _child_line(ledger: Tickets, ticket_id: str) -> str:
    spec = ledger.spec(ticket_id)
    status, verdict = ledger.status(ticket_id)
    note = next((e.note for e in reversed(ledger.history(ticket_id)) if e.note), "")
    outcome = f"{status.value}" + (f" · {verdict.value}" if verdict else "")
    return f"- {ticket_id} {spec.type.value} → {spec.assignee} [{outcome}] {spec.title}: {note[:900]}"
