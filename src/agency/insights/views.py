"""I modelli di lettura di un progetto: gli stessi per `agency report`, il suo JSON e l'API del cruscotto.

Sono modelli propri, non le tabelle della proiezione (ADR-0022): chi legge vede ciò che serve a capire, e
la proiezione può cambiare senza cambiare loro. Il calcolo è puro: dagli stessi dati, lo stesso rapporto.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agency.insights import sums
from agency.insights.domain import Call, ProjectRecord, Provenance
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
    """How the model worked in one phase. The averages count only the measured calls."""

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
    """Up to the approved `concept` gate: what getting there cost, and how long it took."""

    cost_usd: float
    calls: int
    minutes: float


class WaitView(_View):
    """The run stopped for a client decision: from the last call before the gate to the decision."""

    gate: str
    started_at: str
    ended_at: str
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


class InstanceView(_View):
    """An instance on the timeline, from its first call to its last. `model_ms`: the time spent with the
    model."""

    instance: str
    ticket_id: str
    role: str
    phase: str
    started_at: str
    ended_at: str
    calls: int
    cost_usd: float
    model_ms: int | None


class TicketView(_View):
    id: str
    status: str
    verdict: str | None
    assignee: str
    title: str
    cost_usd: float


class ProjectSummary(_View):
    """A project in the list: what it cost, how many calls it made, when it worked."""

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
    started_at: str | None
    ended_at: str | None
    elapsed_minutes: float
    working_minutes: float
    waits: list[WaitView]
    cache_hit: float
    mean_context: float
    parallel: int
    instances: list[InstanceView]
    roles: list[RoleView]
    phases: list[PhaseView]
    ticket_types: list[TypeCost]
    to_presentation: Milestone | None
    ideas: list[IdeaView]
    judgments: list[JudgmentView]
    tickets: list[TicketView]
    provenance: Provenance


def _peak(calls: list[Call]) -> int:
    """Quante istanze hanno lavorato insieme nel momento di massimo: a pari istante, prima chi entra."""
    groups = sums.groups(calls, lambda call: call.instance).values()
    spans = [(min(call.at for call in group), max(call.at for call in group)) for group in groups]
    moments = sorted((at, step) for start, end in spans for at, step in ((start, 0), (end, 1)))
    active = peak = 0
    for _, step in moments:
        active += 1 if step == 0 else -1
        peak = max(peak, active)
    return peak


def _phase(name: str, calls: list[Call]) -> PhaseView:
    return PhaseView(
        phase=name,
        calls=len(calls),
        cost_usd=sums.cost(calls),
        measured=len(sums.measured(calls)),
        mean_duration_ms=sums.mean_duration_ms(calls),
        median_ttft_ms=sums.median_ttft_ms(calls),
        reasoning_tokens=sums.reasoning_tokens(calls),
    )


def _instance(name: str, calls: list[Call]) -> InstanceView:
    first = calls[0]
    return InstanceView(
        instance=name,
        ticket_id=first.ticket_id,
        role=first.role,
        phase=first.phase,
        started_at=min(call.at for call in calls),
        ended_at=max(call.at for call in calls),
        calls=len(calls),
        cost_usd=sums.cost(calls),
        model_ms=sums.model_ms(calls),
    )


def _milestone(data: ProjectData) -> Milestone | None:
    gate = next((gate for gate in data.gates if gate.gate == "concept" and gate.approved), None)
    before = [call for call in data.calls if gate is not None and call.at <= gate.at]
    if not before:
        return None
    return Milestone(
        cost_usd=sums.cost(before), calls=len(before), minutes=sums.minutes(data.calls[0].at, before[-1].at)
    )


def _waits(data: ProjectData) -> list[WaitView]:
    """Ogni decisione ferma il run dall'ultima chiamata, o dalla decisione prima, finché arriva. Conta solo se
    il lavoro è ripartito: una decisione dopo l'ultima chiamata non ha fermato niente. Gli istanti restano
    quelli scritti nel registro."""
    moments = sorted((datetime.fromisoformat(call.at), call.at) for call in data.calls)
    waits: list[WaitView] = []
    previous: tuple[datetime, str] | None = None
    for gate in sorted(data.gates, key=lambda gate: datetime.fromisoformat(gate.at)):
        decided = datetime.fromisoformat(gate.at)
        last_call = next((moment for moment in reversed(moments) if moment[0] <= decided), None)
        start = max((moment for moment in (last_call, previous) if moment is not None), default=None)
        previous = (decided, gate.at)
        resumed = bool(moments) and moments[-1][0] > decided
        if start is None or not resumed or start[0] >= decided:
            continue
        minutes = (decided - start[0]).total_seconds() / 60
        waits.append(WaitView(gate=gate.gate, started_at=start[1], ended_at=gate.at, minutes=minutes))
    return waits


def project_report(name: str, data: ProjectData, provenance: Provenance) -> ProjectReport:
    calls = data.calls
    started_at = min((call.at for call in calls), default=None)
    ended_at = max((call.at for call in calls), default=None)
    elapsed = sums.minutes(started_at, ended_at) if started_at is not None and ended_at is not None else 0.0
    waits = _waits(data)
    context = sum(sums.context(call) for call in calls)
    roles = [
        RoleView(
            role=role,
            calls=len(group),
            cost_usd=sums.cost(group),
            mean_context=sum(sums.context(call) for call in group) / len(group),
            output_tokens=sum(call.output_tokens for call in group),
        )
        for role, group in sums.groups(calls, lambda call: call.role).items()
    ]
    phases = [_phase(phase, group) for phase, group in sums.groups(calls, lambda call: call.phase).items()]
    by_ticket = sums.groups(calls, lambda call: call.ticket_id)
    return ProjectReport(
        project=name,
        budget_usd=data.project.budget_usd if data.project else None,
        model=data.project.model if data.project else "",
        effort=data.project.effort if data.project else "",
        cost_usd=sums.cost(calls),
        calls=len(calls),
        started_at=started_at,
        ended_at=ended_at,
        elapsed_minutes=elapsed,
        working_minutes=elapsed - sum(wait.minutes for wait in waits),
        waits=waits,
        cache_hit=sum(call.cache_read_tokens for call in calls) / context if context else 0.0,
        mean_context=context / len(calls) if calls else 0.0,
        parallel=_peak(calls),
        instances=sorted(
            (
                _instance(name, group)
                for name, group in sums.groups(calls, lambda call: call.instance).items()
            ),
            key=lambda item: (item.started_at, item.instance),
        ),
        roles=sorted(roles, key=lambda role: (-role.cost_usd, role.role)),
        phases=sorted(phases, key=lambda phase: (-phase.cost_usd, phase.phase)),
        ticket_types=[
            TypeCost(ticket_type=kind, cost_usd=sums.cost(group))
            for kind, group in sums.groups(calls, lambda call: call.ticket_type).items()
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
                cost_usd=sums.cost(by_ticket.get(ticket.id, [])),
            )
            for ticket in data.tickets
        ],
        provenance=provenance,
    )


def project_summaries(projects: list[ProjectRecord], calls: list[Call]) -> list[ProjectSummary]:
    """Ogni progetto che il registro conosce, per nome: anche senza chiamate o senza scelte del cliente."""
    budgets = {project.name: project.budget_usd for project in projects}
    by_project = sums.groups(calls, lambda call: call.project)
    names = sorted(budgets.keys() | by_project.keys())
    return [
        ProjectSummary(
            name=name,
            budget_usd=budgets.get(name),
            cost_usd=sums.cost(by_project.get(name, [])),
            calls=len(by_project.get(name, [])),
            first_at=min((call.at for call in by_project.get(name, [])), default=None),
            last_at=max((call.at for call in by_project.get(name, [])), default=None),
        )
        for name in names
    ]
