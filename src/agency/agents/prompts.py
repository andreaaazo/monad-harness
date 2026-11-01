"""Compone il prefisso stabile di ogni ruolo e il pacchetto del ticket."""

from __future__ import annotations

import json

from agency.config import REPO_ROOT
from agency.ledger import Ledger

PROMPTS = REPO_ROOT / "prompts"
ROLES: dict[str, dict] = json.loads((REPO_ROOT / "registry/roles.json").read_text(encoding="utf-8"))["roles"]
ORG: dict[str, list[str]] = json.loads((REPO_ROOT / "registry/org.json").read_text(encoding="utf-8"))[
    "can_open"
]


def skill_names() -> list[str]:
    return sorted(path.parent.name for path in (PROMPTS / "skills").glob("*/SKILL.md"))


def skills_index() -> str:
    return ", ".join(skill_names())


def has_prompt(role: str) -> bool:
    """Un ruolo senza prompt non è ancora stato portato: non può ricevere lavoro."""
    return (PROMPTS / "roles" / f"{role}.md").is_file()


def system_prompt(name: str) -> str:
    """Testo identico tra istanze dello stesso ruolo: niente date né identificativi, o la cache salta."""
    common = (PROMPTS / "common.md").read_text(encoding="utf-8")
    body = (PROMPTS / "roles" / f"{name}.md").read_text(encoding="utf-8")
    return (
        f"{common}\n{body}\nSkill disponibili con read_skill: {skills_index()}; org: craft.md, "
        "anti-patterns.md, lessons.md, review.md."
    )


def packet(ledger: Ledger, ticket_id: str, rework_note: str = "") -> str:
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
    allowed = ORG.get(sender, [])
    return "*" in allowed or assignee in allowed
