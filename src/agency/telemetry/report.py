"""Rapporto di costo: dove sono finiti i soldi di un progetto, e con quale impronta ha lavorato."""

from __future__ import annotations

import json
import re
from datetime import datetime

from agency.contracts.run import Change, Fingerprint, changes
from agency.insights.domain import Provenance
from agency.ledger import Ledger
from agency.ledger.models import ArtifactRow, JudgmentRow, RunRow

SHA256 = re.compile(r"[0-9a-f]{64}")
NAMED = 5  # oltre, l'elenco delle differenze si legge con agency compare


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
    judged = ledger.judgments(project)
    if judged:
        lines += ["", "Giudizi alla cieca:"]
        for row in judged:
            size = len(ledger.comparison(row.comparison))
            lines.append(
                f"  {row.at[:10]} {row.judge}, confronto {row.comparison}: {_verdict(row, size)}. {row.why}"
            )
    lines += ["", "Ticket:"]
    for row in ledger.tickets(project):
        spec = ledger.spec(row.id)
        verdict = f" · {row.verdict}" if row.verdict else ""
        lines.append(
            f"  {row.id} {row.status}{verdict} → {spec.assignee}: {spec.title}"
            f" ({ledger.spent(project, row.id):.2f} $)"
        )
    return "\n".join(lines)


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def _value(value: str | None) -> str:
    if value is None:
        return "assente"
    if value == "":
        return "predefinito"
    return value[:12] if SHA256.fullmatch(value) else value


def _label(change: Change) -> str:
    return change.item or change.part


def _fingerprint(row: RunRow) -> Fingerprint:
    return Fingerprint.model_validate_json(row.fingerprint_json)


def render_runs(ledger: Ledger, project: str) -> str:
    rows = ledger.runs(project)
    if not rows:
        return f"{project}: nessuna esecuzione con impronta. I lavori precedenti a M1.6 non la hanno"
    lines = [f"{project}: {_count(len(rows), 'esecuzione', 'esecuzioni')}"]
    previous: Fingerprint | None = None
    for row in rows:
        current = _fingerprint(row)
        line = f"  #{row.seq:<5}{row.at}  {row.command:8}{row.digest[:12]}"
        if previous is not None:
            found = changes(previous, current)
            names = ", ".join(_label(change) for change in found[:NAMED])
            more = f" e altre {len(found) - NAMED}" if len(found) > NAMED else ""
            count = _count(len(found), "differenza", "differenze")
            line += f"  {count} dalla precedente: {names}{more}" if found else "  identica alla precedente"
        lines.append(line)
        previous = current
    return "\n".join(lines)


def render_comparison(first: RunRow, second: RunRow) -> str:
    found = changes(_fingerprint(first), _fingerprint(second))
    title = f"#{first.seq} {first.project} {first.command} → #{second.seq} {second.project} {second.command}"
    lines = [f"{title}: {_count(len(found), 'differenza', 'differenze') if found else 'nessuna differenza'}"]
    for change in found:
        where = f"{change.part} {change.item}".rstrip()
        lines.append(f"  {where}: {_value(change.before)} → {_value(change.after)}")
    return "\n".join(lines)


def _quality(row: JudgmentRow) -> str:
    return f"{row.level}, {'specifico' if row.specific else 'generico'}"


def _verdict(row: JudgmentRow, size: int) -> str:
    rank = ""
    if size > 1:
        rank = f", il migliore di {size}" if row.best else f", non il migliore di {size}"
    return f"{row.file} [{row.letter}] {_quality(row)}{rank}"


def render_reveal(rows: list[JudgmentRow]) -> str:
    """Dopo il giudizio, e solo allora: quale file c'era dietro ogni lettera."""
    first = rows[0]
    count = _count(len(rows), "giudizio", "giudizi")
    lines = [f"Registrati {count} di {first.judge}, confronto {first.comparison}:"]
    for row in rows:
        best = ", il migliore" if row.best else ""
        origin = f"{row.file} di {row.project}" if row.project else row.file
        lines.append(f"  {row.letter} {_quality(row)}{best}: {origin}")
    return "\n".join(lines)


def _size(size: int) -> str:
    for unit, scale in (("MB", 1 << 20), ("KB", 1 << 10)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}"
    return f"{size} B"


def render_artifacts(rows: list[ArtifactRow], project: str) -> str:
    if not rows:
        return f"{project}: nessuna versione conservata. I lavori precedenti a M1.6 non ne hanno"
    lines = [f"{project}: {_count(len(rows), 'versione conservata', 'versioni conservate')}"]
    for row in rows:
        lines.append(
            f"  {row.sha256[:12]}  {row.origin}  {row.ticket_id or '-'}  {_size(row.size)}  {row.path}"
        )
    return "\n".join(lines)


def render_restored(rows: list[ArtifactRow], destination: str) -> str:
    lines = [f"Ripristinato {destination} dalla versione {rows[0].sha256[:12]}, conservata per:"]
    for row in rows:
        reason = f"{row.origin} di {row.ticket_id}" if row.ticket_id else row.origin
        lines.append(f"  {reason}, {row.project or 'fuori dai progetti'}: {row.path}")
    return "\n".join(lines)


def render_damaged(rows: list[ArtifactRow]) -> str:
    lines = ["ARTEFATTI DANNEGGIATI: queste versioni mancano dal deposito o non hanno più il loro hash"]
    lines += [f"  {row.sha256[:12]}  {row.project or '-'}  {row.path}" for row in rows]
    return "\n".join(lines)


def render_provenance(built: Provenance, path: str) -> str:
    return "\n".join(
        [
            f"Proiezione rigenerata in {path}, dal registro alla revisione {built.registry_revision}:",
            f"  {_count(built.calls, 'chiamata', 'chiamate')}",
            f"  misure: {built.from_registry} dal registro, {built.from_traces} dalle tracce,"
            f" {built.unmeasured} non misurate",
            f"  fasi: {built.phases_recorded} registrate, {built.phases_derived} ricavate",
            f"  righe di traccia illeggibili: {built.unreadable_trace_lines}",
        ]
    )
