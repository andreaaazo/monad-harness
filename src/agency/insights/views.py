"""I modelli di lettura di un progetto: gli stessi per `agency report`, il suo JSON e l'API del cruscotto.

Sono modelli propri, non le tabelle della proiezione (ADR-0022): chi legge vede ciò che serve a capire, e
la proiezione può cambiare senza cambiare loro. Il calcolo è puro: dagli stessi dati, lo stesso rapporto.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agency.insights.domain import Call, Measures, ProjectRecord, Provenance
from agency.insights.ports import ProjectData


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RoleView(_View):
    role: str
    calls: int
    cost_usd: float
    mean_context: float
    output_tokens: int


class PhaseView(_View):
    """Come ha lavorato il modello in una fase. Le medie valgono solo sulle chiamate misurate."""

    phase: str
    calls: int
    cost_usd: float
    measured: int
    mean_duration_ms: float | None
    median_ttft_ms: int | None
    reasoning_tokens: int


class TypeCost(_View):
    ticket_type: str
    cost_usd: float


class Milestone(_View):
    """Fino al gate `concept` approvato: quanto è costato e quanto è durato arrivarci."""

    cost_usd: float
    calls: int
    minutes: float


class IdeaView(_View):
    round: int
    anon: str
    status: str
    lever: str
    concept: str


class JudgmentView(_View):
    at: str
    judge: str
    comparison: str
    file: str
    sha256: str
    letter: str
    level: str
    specific: bool
    best: bool
    compared: int
    why: str


class TicketView(_View):
    id: str
    status: str
    verdict: str | None
    assignee: str
    title: str
    cost_usd: float


class ProjectSummary(_View):
    """Un progetto nell'elenco: quanto è costato, quante chiamate, quando ha lavorato."""

    name: str
    budget_usd: float | None
    cost_usd: float
    calls: int
    first_at: str | None
    last_at: str | None


class ProjectReport(_View):
    project: str
    budget_usd: float | None
    model: str
    effort: str
    cost_usd: float
    calls: int
    cache_hit: float
    mean_context: float
    parallel: int
    roles: list[RoleView]
    phases: list[PhaseView]
    ticket_types: list[TypeCost]
    to_presentation: Milestone | None
    ideas: list[IdeaView]
    judgments: list[JudgmentView]
    tickets: list[TicketView]
    provenance: Provenance


def _context(call: Call) -> int:
    return (
        call.input_tokens + call.cache_read_tokens + call.cache_write_5m_tokens + call.cache_write_1h_tokens
    )


def _groups(calls: Iterable[Call], key: Callable[[Call], str]) -> dict[str, list[Call]]:
    """Le chiamate per chiave, nell'ordine in cui la chiave compare la prima volta."""
    groups: dict[str, list[Call]] = {}
    for call in calls:
        groups.setdefault(key(call), []).append(call)
    return groups


def _cost(calls: Iterable[Call]) -> float:
    return sum(call.cost_usd for call in calls)


def _peak(calls: list[Call]) -> int:
    """Quante istanze hanno lavorato insieme nel momento di massimo: a pari istante, prima chi entra."""
    groups = _groups(calls, lambda call: call.instance).values()
    spans = [(min(call.at for call in group), max(call.at for call in group)) for group in groups]
    moments = sorted((at, step) for start, end in spans for at, step in ((start, 0), (end, 1)))
    active = peak = 0
    for _, step in moments:
        active += 1 if step == 0 else -1
        peak = max(peak, active)
    return peak


def _phase(name: str, calls: list[Call]) -> PhaseView:
    measured = [call for call in calls if call.measures is not Measures.MISSING]
    durations = [call.duration_ms for call in measured if call.duration_ms is not None]
    ttft = [call.ttft_ms for call in measured if call.ttft_ms is not None]
    return PhaseView(
        phase=name,
        calls=len(calls),
        cost_usd=_cost(calls),
        measured=len(measured),
        mean_duration_ms=statistics.fmean(durations) if durations else None,
        median_ttft_ms=statistics.median_low(ttft) if ttft else None,
        reasoning_tokens=sum(call.reasoning_tokens or 0 for call in measured),
    )


def _milestone(data: ProjectData) -> Milestone | None:
    gate = next((gate for gate in data.gates if gate.gate == "concept" and gate.approved), None)
    before = [call for call in data.calls if gate is not None and call.at <= gate.at]
    if not before:
        return None
    elapsed = datetime.fromisoformat(before[-1].at) - datetime.fromisoformat(data.calls[0].at)
    return Milestone(cost_usd=_cost(before), calls=len(before), minutes=elapsed.total_seconds() / 60)


def project_report(name: str, data: ProjectData, provenance: Provenance) -> ProjectReport:
    calls = data.calls
    context = sum(_context(call) for call in calls)
    roles = [
        RoleView(
            role=role,
            calls=len(group),
            cost_usd=_cost(group),
            mean_context=sum(_context(call) for call in group) / len(group),
            output_tokens=sum(call.output_tokens for call in group),
        )
        for role, group in _groups(calls, lambda call: call.role).items()
    ]
    phases = [_phase(phase, group) for phase, group in _groups(calls, lambda call: call.phase).items()]
    by_ticket = _groups(calls, lambda call: call.ticket_id)
    return ProjectReport(
        project=name,
        budget_usd=data.project.budget_usd if data.project else None,
        model=data.project.model if data.project else "",
        effort=data.project.effort if data.project else "",
        cost_usd=_cost(calls),
        calls=len(calls),
        cache_hit=sum(call.cache_read_tokens for call in calls) / context if context else 0.0,
        mean_context=context / len(calls) if calls else 0.0,
        parallel=_peak(calls),
        roles=sorted(roles, key=lambda role: (-role.cost_usd, role.role)),
        phases=sorted(phases, key=lambda phase: (-phase.cost_usd, phase.phase)),
        ticket_types=[
            TypeCost(ticket_type=kind, cost_usd=_cost(group))
            for kind, group in _groups(calls, lambda call: call.ticket_type).items()
        ],
        to_presentation=_milestone(data),
        ideas=[
            IdeaView(
                round=idea.round, anon=idea.anon, status=idea.status, lever=idea.lever, concept=idea.concept
            )
            for idea in data.concepts
        ],
        judgments=[
            JudgmentView(
                at=judged.at,
                judge=judged.judge,
                comparison=judged.comparison,
                file=judged.file,
                sha256=judged.sha256,
                letter=judged.letter,
                level=judged.level,
                specific=judged.specific,
                best=judged.best,
                compared=judged.compared,
                why=judged.why,
            )
            for judged in data.judgments
        ],
        tickets=[
            TicketView(
                id=ticket.id,
                status=ticket.status,
                verdict=ticket.verdict,
                assignee=ticket.assignee,
                title=ticket.title,
                cost_usd=_cost(by_ticket.get(ticket.id, [])),
            )
            for ticket in data.tickets
        ],
        provenance=provenance,
    )


def project_summaries(projects: list[ProjectRecord], calls: list[Call]) -> list[ProjectSummary]:
    """Ogni progetto che il registro conosce, per nome: anche senza chiamate o senza scelte del cliente."""
    budgets = {project.name: project.budget_usd for project in projects}
    by_project = _groups(calls, lambda call: call.project)
    names = sorted(budgets.keys() | by_project.keys())
    return [
        ProjectSummary(
            name=name,
            budget_usd=budgets.get(name),
            cost_usd=_cost(by_project.get(name, [])),
            calls=len(by_project.get(name, [])),
            first_at=min((call.at for call in by_project.get(name, [])), default=None),
            last_at=max((call.at for call in by_project.get(name, [])), default=None),
        )
        for name in names
    ]
