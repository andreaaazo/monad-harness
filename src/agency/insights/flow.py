"""La vista Fasi: dalle idee alla consegna, dove il lavoro si è fermato o è tornato indietro.

Tutto viene dalla storia dei ticket nel registro. Un rimando del direttore è lavoro da rifare: ciò che il
ticket costa dopo il primo rimando è lavoro rifatto. Un ticket bloccato è costato senza dare un esito. Il nome
delle istanze non dice niente di questo, perché il direttore ne apre una nuova a ogni turno.

La fase di un ticket è quella del motore: il prompt del ticket, poi il ruolo di chi lo riceve. La consegna
al cliente non sta in una fase: è il progetto, e il suo stato è l'esito.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agency.contracts import phase
from agency.contracts.ticket import Status, TicketType
from agency.insights import sums
from agency.insights.domain import SETBACKS, Call, EventRecord, Lifecycle, TicketRecord
from agency.insights.ports import ProjectData

# Un ticket non ha finito finché è aperto, da rifare o consegnato senza essere accettato. La consegna al
# cliente fa eccezione: consegnata, il progetto è finito.
UNFINISHED = frozenset({Status.OPEN, Status.REWORK, Status.DELIVERED})


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Step(_View):
    """Un passo nella storia di un ticket. `setback`: un rimando, un blocco o un annullamento."""

    at: str
    action: Lifecycle
    actor: str
    setback: bool


class TicketFlow(_View):
    """Un ticket dall'apertura all'ultimo passo. `redone_usd`: ciò che è costato dopo il primo rimando."""

    id: str
    title: str
    type: str
    assignee: str
    phase: str
    status: str
    verdict: str | None
    calls: int
    cost_usd: float
    redone_usd: float
    deliveries: int
    reworks: int
    steps: list[Step]


class PhaseFlow(_View):
    """Una fase: quanto è costata e quanto lavoro è tornato indietro. `started_at` è la prima chiamata."""

    phase: str
    started_at: str | None
    ended_at: str | None
    calls: int
    cost_usd: float
    tickets: int
    deliveries: int
    reworks: int
    blocked: int
    redone_usd: float
    blocked_usd: float


class Setback(_View):
    """Un passo indietro: un ticket rimandato, bloccato o annullato, dopo quante consegne, e perché, con le
    parole di chi lo ha fatto."""

    at: str
    action: Lifecycle
    actor: str
    ticket_id: str
    title: str
    phase: str
    after_deliveries: int
    reason: str


class Outcome(_View):
    """Dove si è fermato il progetto: la consegna al cliente, ciò che resta da finire, l'ultimo passo."""

    delivery_id: str | None
    delivery_status: str | None
    unfinished: list[str]
    last_at: str | None
    last_action: Lifecycle | None
    last_ticket_id: str | None


class FlowReport(_View):
    project: str
    outcome: Outcome
    phases: list[PhaseFlow]
    setbacks: list[Setback]
    tickets: list[TicketFlow]


def ticket_phase(ticket: TicketRecord) -> str:
    return phase.of(ticket.assignee, ticket.prompt)


def _ticket(ticket: TicketRecord, calls: list[Call], events: list[EventRecord]) -> TicketFlow:
    reworks = [event for event in events if event.action is Lifecycle.REWORK]
    first_rework = datetime.fromisoformat(reworks[0].at) if reworks else None
    redone = [
        call for call in calls if first_rework is not None and datetime.fromisoformat(call.at) > first_rework
    ]
    return TicketFlow(
        id=ticket.id,
        title=ticket.title,
        type=ticket.type,
        assignee=ticket.assignee,
        phase=ticket_phase(ticket),
        status=ticket.status,
        verdict=ticket.verdict,
        calls=len(calls),
        cost_usd=sums.cost(calls),
        redone_usd=sums.cost(redone),
        deliveries=sum(1 for event in events if event.action is Lifecycle.DELIVER),
        reworks=len(reworks),
        steps=[
            Step(at=event.at, action=event.action, actor=event.actor, setback=event.action in SETBACKS)
            for event in events
        ],
    )


def _phase(name: str, calls: list[Call], tickets: list[TicketFlow]) -> PhaseFlow:
    blocked = [ticket for ticket in tickets if ticket.status == Status.BLOCKED]
    return PhaseFlow(
        phase=name,
        started_at=min((call.at for call in calls), default=None),
        ended_at=max((call.at for call in calls), default=None),
        calls=len(calls),
        cost_usd=sums.cost(calls),
        tickets=len(tickets),
        deliveries=sum(ticket.deliveries for ticket in tickets),
        reworks=sum(ticket.reworks for ticket in tickets),
        blocked=len(blocked),
        redone_usd=sum(ticket.redone_usd for ticket in tickets),
        blocked_usd=sum(ticket.cost_usd for ticket in blocked),
    )


def setbacks(events: list[EventRecord], tickets: dict[str, TicketRecord]) -> list[Setback]:
    """I passi indietro in ordine di tempo: li leggono la vista Fasi e la vista Strumenti e QA."""
    setbacks: list[Setback] = []
    delivered: dict[str, int] = {}
    for event in sorted(events, key=lambda event: event.seq):
        if event.action is Lifecycle.DELIVER:
            delivered[event.ticket_id] = delivered.get(event.ticket_id, 0) + 1
        ticket = tickets.get(event.ticket_id)
        if event.action not in SETBACKS or ticket is None:
            continue
        setbacks.append(
            Setback(
                at=event.at,
                action=event.action,
                actor=event.actor,
                ticket_id=ticket.id,
                title=ticket.title,
                phase=ticket_phase(ticket),
                after_deliveries=delivered.get(event.ticket_id, 0),
                reason=event.reason or "",
            )
        )
    return setbacks


def _outcome(tickets: list[TicketRecord], events: list[EventRecord]) -> Outcome:
    delivery = next((ticket for ticket in tickets if ticket.type == TicketType.DELIVERY), None)
    last = max(events, key=lambda event: event.seq, default=None)
    return Outcome(
        delivery_id=delivery.id if delivery else None,
        delivery_status=delivery.status if delivery else None,
        unfinished=sorted(
            ticket.id
            for ticket in tickets
            if ticket.type != TicketType.DELIVERY and ticket.status in UNFINISHED
        ),
        last_at=last.at if last else None,
        last_action=last.action if last else None,
        last_ticket_id=last.ticket_id if last else None,
    )


def flow_report(name: str, data: ProjectData) -> FlowReport:
    calls_by_ticket = sums.groups(data.calls, lambda call: call.ticket_id)
    events_by_ticket = sums.groups(
        sorted(data.events, key=lambda event: event.seq), lambda event: event.ticket_id
    )
    tickets = [
        _ticket(ticket, calls_by_ticket.get(ticket.id, []), events_by_ticket.get(ticket.id, []))
        for ticket in sorted(data.tickets, key=lambda ticket: ticket.id)
    ]
    calls_by_phase = sums.groups(data.calls, lambda call: call.phase)
    # La consegna al cliente è il progetto, non una fase: il suo stato sta nell'esito.
    worked = [ticket for ticket in tickets if ticket.type != TicketType.DELIVERY]
    tickets_by_phase = sums.groups(worked, lambda ticket: ticket.phase)
    opened = {ticket.id: ticket.created_at for ticket in data.tickets}

    def begins(name: str) -> datetime:
        """In ordine di lavoro: dalla prima chiamata, o dall'apertura del primo ticket se non ne ha."""
        moments = [call.at for call in calls_by_phase.get(name, [])] or [
            opened[ticket.id] for ticket in tickets_by_phase.get(name, [])
        ]
        return min(datetime.fromisoformat(moment) for moment in moments)

    names = sorted({*calls_by_phase, *tickets_by_phase}, key=begins)
    return FlowReport(
        project=name,
        outcome=_outcome(data.tickets, data.events),
        phases=[_phase(item, calls_by_phase.get(item, []), tickets_by_phase.get(item, [])) for item in names],
        setbacks=setbacks(data.events, {ticket.id: ticket for ticket in data.tickets}),
        tickets=tickets,
    )
