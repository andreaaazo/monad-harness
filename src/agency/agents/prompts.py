"""Builds each role's stable system prompt and the ticket packet an instance starts from."""

from __future__ import annotations

import json

from agency.config import REPO_ROOT
from agency.contracts.registry import read_org, read_roles
from agency.ledger import Ledger

PROMPTS = REPO_ROOT / "prompts"
ROLES: dict[str, dict] = read_roles(REPO_ROOT / "registry/roles.json")
ORG: dict[str, list[str]] = read_org(REPO_ROOT / "registry/org.json")


def skill_names() -> list[str]:
    """The skills `read_skill` serves: the folders under prompts/skills that hold a SKILL.md."""
    return sorted(path.parent.name for path in (PROMPTS / "skills").glob("*/SKILL.md"))


def skills_index() -> str:
    """The skill names as the system prompt lists them."""
    return ", ".join(skill_names())


def has_prompt(role: str) -> bool:
    """A role without a prompt has not been ported yet: it cannot receive work."""
    return (PROMPTS / "roles" / f"{role}.md").is_file()


def system_prompt(name: str) -> str:
    """Identical across the instances of a role: no dates or ids, or the prompt cache misses."""
    common = (PROMPTS / "common.md").read_text(encoding="utf-8")
    body = (PROMPTS / "roles" / f"{name}.md").read_text(encoding="utf-8")
    return (
        f"{common}\n{body}\nSkill disponibili con read_skill: {skills_index()}; org: craft.md, "
        "anti-patterns.md, lessons.md, review.md."
    )


def packet(ledger: Ledger, ticket_id: str, rework_note: str = "") -> str:
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


def _child_line(ledger: Ledger, ticket_id: str) -> str:
    spec = ledger.spec(ticket_id)
    status, verdict = ledger.status(ticket_id)
    note = next((e.note for e in reversed(ledger.history(ticket_id)) if e.note), "")
    outcome = f"{status.value}" + (f" · {verdict.value}" if verdict else "")
    return f"- {ticket_id} {spec.type.value} → {spec.assignee} [{outcome}] {spec.title}: {note[:900]}"


def can_open(sender: str, assignee: str) -> bool:
    """Whether `sender` may open a ticket for `assignee`, by registry/org.json (`*` allows anyone)."""
    allowed = ORG.get(sender, [])
    return "*" in allowed or assignee in allowed
