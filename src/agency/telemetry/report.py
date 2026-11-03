"""Rapporto di costo: dove sono finiti i soldi di un progetto, e con quale impronta ha lavorato."""

from __future__ import annotations

import re

from agency.contracts.run import Change, Fingerprint, changes
from agency.insights.domain import Provenance
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from agency.ledger.models import ArtifactRow, JudgmentRow, RunRow

SHA256 = re.compile(r"[0-9a-f]{64}")
NAMED = 5  # oltre, l'elenco delle differenze si legge con agency compare


def _seconds(milliseconds: float | None) -> str:
    return f"{milliseconds / 1000:.1f} s" if milliseconds is not None else "-"


def render(view: ProjectReport) -> str:
    """Il rapporto di un progetto in testo, dallo stesso modello del JSON e del cruscotto."""
    budget = f" su {view.budget_usd:.2f} $" if view.budget_usd is not None else ""
    choice = f", modello {view.model}" if view.model else ""
    choice += f", effort {view.effort}" if view.effort else ""
    lines = [
        f"Progetto {view.project}: {view.cost_usd:.2f} ${budget} in {view.calls} chiamate{choice}",
        f"Cache: {view.cache_hit:.0%} dei token in ingresso letti dalla cache",
        f"Contesto medio per chiamata: {view.mean_context:,.0f} token",
        f"Istanze in parallelo: {view.parallel}",
        "",
        f"{'ruolo':22}{'chiamate':>9}{'costo $':>10}{'contesto medio':>16}{'output':>9}",
    ]
    for role in view.roles:
        lines.append(
            f"{role.role:22}{role.calls:>9}{role.cost_usd:>10.3f}{role.mean_context:>16,.0f}{role.output_tokens:>9,}"
        )
    if view.phases:
        measured = sum(phase.measured for phase in view.phases)
        lines += [
            "",
            f"Per fase, con le misure di {measured} chiamate su {view.calls}:",
            f"{'fase':22}{'chiamate':>9}{'costo $':>10}{'durata media':>14}{'TTFT mediano':>14}"
            f"{'ragionamento':>14}",
        ]
        for phase in view.phases:
            lines.append(
                f"{phase.phase:22}{phase.calls:>9}{phase.cost_usd:>10.3f}{_seconds(phase.mean_duration_ms):>14}"
                f"{_seconds(phase.median_ttft_ms):>14}{phase.reasoning_tokens:>14,}"
            )
    if view.ticket_types:
        costs = ", ".join(
            f"{item.ticket_type or 'senza ticket'} {item.cost_usd:.2f} $" for item in view.ticket_types
        )
        lines += ["", f"Costo per tipo di lavoro: {costs}"]
    if view.to_presentation:
        milestone = view.to_presentation
        lines += [
            "",
            f"Fino alla presentazione: {milestone.cost_usd:.2f} $ in {milestone.minutes:.1f} minuti",
        ]
    if view.ideas:
        lines += ["", "Idee:"]
        for idea in view.ideas:
            lines.append(
                f"  r{idea.round} {idea.anon or '-'} [{idea.status}] {idea.lever[:40]}: {idea.concept[:80]}"
            )
    if view.judgments:
        lines += ["", "Giudizi alla cieca:"]
        for judged in view.judgments:
            rank = ""
            if judged.compared > 1:
                rank = (
                    f", il migliore di {judged.compared}"
                    if judged.best
                    else f", non il migliore di {judged.compared}"
                )
            verdict = f"{judged.file} [{judged.letter}] {_quality(judged.level, judged.specific)}{rank}"
            lines.append(
                f"  {judged.at[:10]} {judged.judge}, confronto {judged.comparison}: {verdict}. {judged.why}"
            )
    lines += ["", "Ticket:"]
    for ticket in view.tickets:
        verdict = f" · {ticket.verdict}" if ticket.verdict else ""
        lines.append(
            f"  {ticket.id} {ticket.status}{verdict} → {ticket.assignee}: {ticket.title}"
            f" ({ticket.cost_usd:.2f} $)"
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


def _quality(level: str, specific: bool) -> str:
    return f"{level}, {'specifico' if specific else 'generico'}"


def render_reveal(rows: list[JudgmentRow]) -> str:
    """Dopo il giudizio, e solo allora: quale file c'era dietro ogni lettera."""
    first = rows[0]
    count = _count(len(rows), "giudizio", "giudizi")
    lines = [f"Registrati {count} di {first.judge}, confronto {first.comparison}:"]
    for row in rows:
        best = ", il migliore" if row.best else ""
        origin = f"{row.file} di {row.project}" if row.project else row.file
        lines.append(f"  {row.letter} {_quality(row.level, row.specific)}{best}: {origin}")
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
            f"  righe di trascrizione illeggibili: {built.unreadable_transcript_lines}",
        ]
    )
