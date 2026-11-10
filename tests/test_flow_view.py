"""La vista Fasi: dalle idee alla consegna, dove il lavoro si è fermato o è tornato indietro."""

from __future__ import annotations

from agency.insights import flow
from agency.insights.domain import SETBACKS, Call, EventRecord, Lifecycle, Measures, PhaseSource, TicketRecord
from agency.insights.ports import ProjectData


def at(minute: int) -> str:
    return f"2026-11-02T10:{minute:02d}:00+00:00"


def call(
    seq: int, minute: int, ticket_id: str, role: str, phase: str, cost_usd: float, instance: str
) -> Call:
    return Call(
        seq=seq,
        at=at(minute),
        project="officina",
        run=None,
        ticket_id=ticket_id,
        ticket_type="",
        role=role,
        instance=instance,
        phase=phase,
        phase_source=PhaseSource.RECORDED,
        model="claude-opus-5-5",
        effort=None,
        input_tokens=100,
        output_tokens=10,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        cost_usd=cost_usd,
        stop_reason="tool_use",
        request_id=f"req_{seq}",
        duration_ms=None,
        ttft_ms=None,
        reasoning_tokens=None,
        measures=Measures.MISSING,
    )


def ticket(id_: str, type_: str, assignee: str, status: str, minute: int, prompt: str = "") -> TicketRecord:
    return TicketRecord(
        id=id_,
        project="officina",
        type=type_,
        assignee=assignee,
        prompt=prompt,
        title=f"Titolo {id_}",
        status=status,
        verdict=None,
        created_at=at(minute),
    )


def event(seq: int, minute: int, ticket_id: str, actor: str, action: Lifecycle) -> EventRecord:
    """Come lo legge il registro: il motivo c'è solo per un passo indietro."""
    reason = f"Motivo del passo {seq}" if action in SETBACKS else None
    return EventRecord(
        seq=seq,
        at=at(minute),
        project="officina",
        ticket_id=ticket_id,
        actor=actor,
        action=action,
        reason=reason,
    )


DIRECTOR = "design-director"
TICKETS = [
    ticket("T-0001", "consegna", DIRECTOR, "open", 0),
    ticket("T-0002", "schizzo", "direction-a", "accepted", 1, "explorer"),
    ticket("T-0003", "schizzo", "direction-b", "accepted", 1, "explorer"),
    ticket("T-0004", "produzione", "identity-designer", "accepted", 20, "finisher"),
    ticket("T-0005", "revisione", "critic", "blocked", 26),
    ticket("T-0006", "qa", "qa-inspector", "open", 50),
]
CALLS = [
    call(1, 0, "T-0001", DIRECTOR, "director-plan", 0.5, "T-0001-a1-plan"),
    call(2, 3, "T-0002", "direction-a", "explorer", 1.0, "T-0002-a1"),
    call(3, 4, "T-0003", "direction-b", "explorer", 2.0, "T-0003-a1"),
    call(4, 22, "T-0004", "identity-designer", "finisher", 3.0, "T-0004-a1"),
    call(5, 27, "T-0005", "critic", "critic", 0.25, "T-0005-a1"),
    call(6, 32, "T-0004", "identity-designer", "finisher", 4.0, "T-0004-a2"),
    call(7, 33, "T-0004", "identity-designer", "finisher", 1.0, "T-0004-a2"),
    call(8, 35, "T-0001", DIRECTOR, DIRECTOR, 0.5, "T-0001-a2"),
]
EVENTS = [
    event(1, 0, "T-0001", "router", Lifecycle.OPEN),
    event(2, 1, "T-0002", DIRECTOR, Lifecycle.OPEN),
    event(3, 1, "T-0003", DIRECTOR, Lifecycle.OPEN),
    event(4, 5, "T-0002", "direction-a", Lifecycle.DELIVER),
    event(5, 6, "T-0003", "direction-b", Lifecycle.DELIVER),
    event(6, 10, "T-0002", DIRECTOR, Lifecycle.ACCEPT),
    event(7, 10, "T-0003", DIRECTOR, Lifecycle.ACCEPT),
    event(8, 20, "T-0004", DIRECTOR, Lifecycle.OPEN),
    event(9, 25, "T-0004", "identity-designer", Lifecycle.DELIVER),
    event(10, 26, "T-0005", DIRECTOR, Lifecycle.OPEN),
    event(11, 28, "T-0005", "critic", Lifecycle.BLOCK),
    event(12, 30, "T-0004", DIRECTOR, Lifecycle.REWORK),
    event(13, 34, "T-0004", "identity-designer", Lifecycle.DELIVER),
    event(14, 36, "T-0004", DIRECTOR, Lifecycle.ACCEPT),
    event(15, 50, "T-0006", DIRECTOR, Lifecycle.OPEN),
]


def data(**extra: object) -> ProjectData:
    base: dict[str, object] = {
        "project": None,
        "calls": CALLS,
        "tickets": TICKETS,
        "gates": [],
        "concepts": [],
        "judgments": [],
        "events": EVENTS,
        "checks": [],
        "tool_calls": [],
        "runs": [],
    }
    return ProjectData.model_validate(base | extra)


def test_phases_follow_the_work_from_the_first_call_and_a_ticket_belongs_to_the_phase_of_its_prompt() -> None:
    """L'ordine è quello del lavoro, non del costo. La fase di un ticket è la regola del motore: il prompt,
    poi il ruolo. Una fase senza chiamate, come un QA appena aperto, viene quando si apre il suo ticket. La
    consegna al cliente non è una fase: è il progetto, e il suo stato sta nell'esito."""
    report = flow.flow_report("officina", data())
    assert [(item.phase, item.started_at, item.tickets) for item in report.phases] == [
        ("director-plan", at(0), 0),
        ("explorer", at(3), 2),
        ("finisher", at(22), 1),
        ("critic", at(27), 1),
        ("design-director", at(35), 0),
        ("qa-inspector", None, 1),
    ]
    assert "T-0001" in [item.id for item in report.tickets]


def test_a_delivery_without_calls_of_its_own_phase_adds_no_empty_phase() -> None:
    calls = [item for item in CALLS if item.phase != DIRECTOR]
    assert DIRECTOR not in [item.phase for item in flow.flow_report("officina", data(calls=calls)).phases]


def test_work_after_the_first_rework_is_redone_and_a_blocked_ticket_has_no_outcome() -> None:
    """Il rimando del minuto 30: le due chiamate dopo sono lavoro rifatto. La revisione bloccata è costata
    senza un esito. Il nome dell'istanza non conta: il direttore ne apre una nuova a ogni turno."""
    report = flow.flow_report("officina", data())
    phases = {item.phase: item for item in report.phases}
    finisher, critic, director = phases["finisher"], phases["critic"], phases["design-director"]
    assert (finisher.cost_usd, finisher.deliveries, finisher.reworks, finisher.redone_usd) == (8.0, 2, 1, 5.0)
    assert (finisher.blocked, finisher.blocked_usd) == (0, 0.0)
    assert (critic.blocked, critic.blocked_usd, critic.redone_usd) == (1, 0.25, 0.0)
    assert (director.reworks, director.redone_usd, director.blocked) == (0, 0.0, 0)
    (production,) = [item for item in report.tickets if item.id == "T-0004"]
    assert (production.deliveries, production.reworks, production.redone_usd, production.cost_usd) == (
        2,
        1,
        5.0,
        8.0,
    )
    assert [(step.action, step.actor, step.setback) for step in production.steps] == [
        (Lifecycle.OPEN, DIRECTOR, False),
        (Lifecycle.DELIVER, "identity-designer", False),
        (Lifecycle.REWORK, DIRECTOR, True),
        (Lifecycle.DELIVER, "identity-designer", False),
        (Lifecycle.ACCEPT, DIRECTOR, False),
    ]


def test_redone_work_starts_at_the_first_rework_not_the_last() -> None:
    """Due rimandi: è rifatto tutto ciò che viene dopo il primo, anche fra il primo e il secondo."""
    tickets = [ticket("T-0004", "produzione", "identity-designer", "accepted", 0, "finisher")]
    calls = [
        call(1, 1, "T-0004", "identity-designer", "finisher", 1.0, "T-0004-a1"),
        call(2, 3, "T-0004", "identity-designer", "finisher", 2.0, "T-0004-a2"),
        call(3, 5, "T-0004", "identity-designer", "finisher", 4.0, "T-0004-a3"),
    ]
    events = [
        event(1, 2, "T-0004", DIRECTOR, Lifecycle.REWORK),
        event(2, 4, "T-0004", DIRECTOR, Lifecycle.REWORK),
    ]
    (production,) = flow.flow_report("officina", data(tickets=tickets, calls=calls, events=events)).tickets
    assert (production.reworks, production.redone_usd) == (2, 6.0)


def test_a_call_that_ends_as_the_rework_arrives_belongs_to_the_attempt_before() -> None:
    tickets = [ticket("T-0004", "produzione", "identity-designer", "rework", 0, "finisher")]
    calls = [call(1, 2, "T-0004", "identity-designer", "finisher", 1.0, "T-0004-a1")]
    events = [event(1, 2, "T-0004", DIRECTOR, Lifecycle.REWORK)]
    (production,) = flow.flow_report("officina", data(tickets=tickets, calls=calls, events=events)).tickets
    assert production.redone_usd == 0.0


def test_setbacks_are_every_step_back_in_order_with_how_many_deliveries_came_before() -> None:
    report = flow.flow_report("officina", data())
    assert [
        (item.at, item.action, item.ticket_id, item.phase, item.after_deliveries, item.reason)
        for item in report.setbacks
    ] == [
        (at(28), Lifecycle.BLOCK, "T-0005", "critic", 0, "Motivo del passo 11"),
        (at(30), Lifecycle.REWORK, "T-0004", "finisher", 1, "Motivo del passo 12"),
    ]
    assert report.setbacks[0].title == "Titolo T-0005"


def test_tickets_and_unfinished_keep_the_incoming_order_past_ten_thousand() -> None:
    tickets = [
        ticket("T-9999", "qa", "critic", "open", 1),
        ticket("T-10000", "qa", "critic", "open", 2),
    ]
    report = flow.flow_report("officina", data(tickets=tickets, calls=[], events=[]))
    assert [item.id for item in report.tickets] == ["T-9999", "T-10000"]
    assert report.outcome.unfinished == ["T-9999", "T-10000"]


def test_the_outcome_says_where_the_project_stopped() -> None:
    """La consegna al cliente è aperta; restano il QA appena aperto. Consegnato e accettato è finito, come
    bloccato: il blocco sta fra i passi indietro."""
    outcome = flow.flow_report("officina", data()).outcome
    assert (outcome.delivery_id, outcome.delivery_status) == ("T-0001", "open")
    assert outcome.unfinished == ["T-0006"]
    assert (outcome.last_at, outcome.last_action, outcome.last_ticket_id) == (
        at(50),
        Lifecycle.OPEN,
        "T-0006",
    )


def test_a_delivered_ticket_waits_for_acceptance_but_the_delivery_to_the_client_is_the_end() -> None:
    tickets = [
        ticket("T-0001", "consegna", DIRECTOR, "delivered", 0),
        ticket("T-0002", "qa", "qa-inspector", "delivered", 1),
        ticket("T-0003", "produzione", "identity-designer", "rework", 1, "finisher"),
    ]
    outcome = flow.flow_report("officina", data(tickets=tickets, events=[], calls=[])).outcome
    assert (outcome.delivery_status, outcome.unfinished) == ("delivered", ["T-0002", "T-0003"])
    assert (outcome.last_at, outcome.last_action, outcome.last_ticket_id) == (None, None, None)


def test_a_project_without_tickets_has_an_empty_flow() -> None:
    report = flow.flow_report("fantasma", data(tickets=[], events=[], calls=[]))
    assert (report.phases, report.setbacks, report.tickets) == ([], [], [])
    assert (report.outcome.delivery_id, report.outcome.delivery_status, report.outcome.unfinished) == (
        None,
        None,
        [],
    )
