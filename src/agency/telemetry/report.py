"""Rapporto di costo: dove sono finiti i soldi di un progetto."""

from __future__ import annotations

import json
from datetime import datetime

from agency.ledger import Ledger


def _context(row) -> int:  # type: ignore[no-untyped-def]
    return row.input_tokens + row.cache_read_tokens + row.cache_write_5m_tokens + row.cache_write_1h_tokens


def _peak(spans: list[tuple[str, str, str]]) -> int:
    """Quante istanze hanno lavorato insieme nel momento di massimo: a pari istante, prima chi entra."""
    moments = sorted((at, step) for start, end, _ in spans for at, step in ((start, 0), (end, 1)))
    active = peak = 0
    for _, step in moments:
        active += 1 if step == 0 else -1
        peak = max(peak, active)
    return peak


def summary(ledger: Ledger, project: str) -> dict:
    rows = ledger.usage(project)
    roles: dict[str, dict] = {}
    for row in rows:
        item = roles.setdefault(row.role, {"calls": 0, "cost": 0.0, "context": 0, "output": 0})
        item["calls"] += 1
        item["cost"] += row.cost_usd
        item["context"] += _context(row)
        item["output"] += row.output_tokens
    read = sum(row.cache_read_tokens for row in rows)
    total_input = sum(_context(row) for row in rows)
    instances: dict[str, list[str]] = {}
    for row in rows:
        instances.setdefault(row.instance, []).append(row.at)
    spans = sorted((min(times), max(times), name) for name, times in instances.items())
    parallel = _peak(spans)
    gate = next((g for g in ledger.gates(project) if g.gate == "concept" and g.approved), None)
    concept = None
    if gate and rows:
        before = [row for row in rows if row.at <= gate.at]
        concept = {"cost": sum(row.cost_usd for row in before), "last": before[-1].at if before else ""}
    return {
        "parallel": parallel,
        "concept": concept,
        "first_at": rows[0].at if rows else "",
        "calls": len(rows),
        "cost": sum(row.cost_usd for row in rows),
        "cache_hit": read / total_input if total_input else 0.0,
        "mean_context": total_input / len(rows) if rows else 0.0,
        "first_context": {row.role: _context(row) for row in reversed(rows)},
        "roles": roles,
    }


def render(ledger: Ledger, project: str) -> str:
    data = summary(ledger, project)
    row = ledger.project(project)
    budget = f" su {row.budget_usd:.2f} $" if row else ""
    choice = f", modello {row.model}" if row and row.model else ""
    choice += f", effort {row.effort}" if row and row.effort else ""
    lines = [
        f"Progetto {project}: {data['cost']:.2f} ${budget} in {data['calls']} chiamate{choice}",
        f"Cache: {data['cache_hit']:.0%} dei token in ingresso letti dalla cache",
        f"Contesto medio per chiamata: {data['mean_context']:,.0f} token",
        f"Istanze in parallelo: {data['parallel']}",
        "",
        f"{'ruolo':22}{'chiamate':>9}{'costo $':>10}{'contesto medio':>16}{'output':>9}",
    ]
    for role, item in sorted(data["roles"].items(), key=lambda pair: -pair[1]["cost"]):
        mean = item["context"] / item["calls"]
        lines.append(f"{role:22}{item['calls']:>9}{item['cost']:>10.3f}{mean:>16,.0f}{item['output']:>9,}")
    phases: dict[str, float] = {}
    for row in ledger.usage(project):
        kind = ledger.spec(row.ticket_id).type.value
        phases[kind] = phases.get(kind, 0.0) + row.cost_usd
    if phases:
        lines += ["", "Costo per tipo di lavoro: " + ", ".join(f"{k} {v:.2f} $" for k, v in phases.items())]
    if data["concept"]:
        start = datetime.fromisoformat(data["first_at"])
        reached = datetime.fromisoformat(data["concept"]["last"])
        minutes = (reached - start).total_seconds() / 60
        lines += ["", f"Fino alla presentazione: {data['concept']['cost']:.2f} $ in {minutes:.1f} minuti"]
    concepts = ledger.concepts(project)
    if concepts:
        lines += ["", "Idee:"]
        for row in concepts:
            card = json.loads(row.card_json).get("concept", "")
            lines.append(f"  r{row.round} {row.anon or '-'} [{row.status}] {row.lever[:40]}: {card[:80]}")
    lines += ["", "Ticket:"]
    for row in ledger.tickets(project):
        spec = ledger.spec(row.id)
        verdict = f" · {row.verdict}" if row.verdict else ""
        lines.append(
            f"  {row.id} {row.status}{verdict} → {spec.assignee}: {spec.title}"
            f" ({ledger.spent(project, row.id):.2f} $)"
        )
    return "\n".join(lines)
