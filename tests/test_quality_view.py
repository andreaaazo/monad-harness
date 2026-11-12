"""The tools and QA view: where the work goes wrong, in the words of whoever said no."""

from __future__ import annotations

from agency.insights import quality
from agency.insights.domain import (
    Call,
    CheckRecord,
    EventRecord,
    Lifecycle,
    Measures,
    PhaseSource,
    TicketRecord,
    ToolCallRecord,
)
from agency.insights.ports import ProjectData


def at(minute: int) -> str:
    return f"2026-11-02T10:{minute:02d}:00+00:00"


def call(seq: int, minute: int, instance: str, ticket_id: str, role: str, phase: str) -> Call:
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
        cost_usd=1.0,
        stop_reason="tool_use",
        request_id=f"req_{seq}",
        duration_ms=None,
        ttft_ms=None,
        reasoning_tokens=None,
        measures=Measures.MISSING,
    )


def ticket(id_: str, assignee: str, status: str, prompt: str = "") -> TicketRecord:
    return TicketRecord(
        id=id_,
        project="officina",
        type="produzione",
        assignee=assignee,
        prompt=prompt,
        title=f"Titolo {id_}",
        status=status,
        verdict=None,
        created_at=at(0),
    )


def check(seq: int, ticket_id: str, file: str, name: str, result: str, reason: str = "") -> CheckRecord:
    return CheckRecord(
        seq=seq,
        at=at(seq),
        project="officina",
        ticket_id=ticket_id,
        file=file,
        check_name=name,
        result=result,
        signer="tool",
        reason=reason,
    )


def tool(seq: int, instance: str, turn: int, name: str, refusal: str | None = None) -> ToolCallRecord:
    return ToolCallRecord(
        seq=seq, project="officina", instance=instance, turn=turn, tool=name, refusal=refusal
    )


TICKETS = [
    ticket("T-0004", "identity-designer", "accepted", "finisher"),
    ticket("T-0005", "critic", "blocked"),
]
CALLS = [
    call(1, 1, "T-0004-a1", "T-0004", "identity-designer", "finisher"),
    call(2, 9, "T-0005-a1", "T-0005", "critic", "critic"),
]
CHECKS = [
    check(1, "T-0004", "segno.svg", "svg_audit", "FAIL", "3 nodi sottotracciati"),
    check(2, "T-0004", "favicon.svg", "svg_audit", "PASS"),
    check(3, "T-0004", "segno.svg", "svg_audit", "FAIL", "ancora 1 nodo"),
    check(4, "T-0004", "segno.svg", "svg_audit", "PASS"),
    check(5, "T-0004", "segno.svg", "logo_proof", "NOT_APPLICABLE"),
    check(6, "T-0005", "segno.svg", "visual_review", "FAIL", "La coda sparisce a 16 px"),
    check(7, "T-0005", "segno.svg", "optical_check", "MEASURED", "spessori misurati"),
]
TOOL_CALLS = [
    tool(1, "T-0004-a1", 1, "view_image"),
    tool(2, "T-0004-a1", 2, "deliver", "consegna rifiutata:\nsegno.svg: 'svg_audit' è FAIL"),
    tool(3, "T-0004-a1", 4, "deliver"),
    tool(4, "T-0005-a1", 1, "view_image"),
    tool(5, "T-0005-a1", 2, "write_file", "un revisore scrive solo in reviews/"),
    tool(6, "T-0005-a1", 3, "view_image"),
]
EVENTS = [
    EventRecord(
        seq=1,
        at=at(10),
        project="officina",
        ticket_id="T-0005",
        actor="critic",
        action=Lifecycle.BLOCK,
        reason="Il contratto chiede review/, ma posso scrivere solo in reviews/",
    )
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
        "checks": CHECKS,
        "tool_calls": TOOL_CALLS,
        "runs": [],
    }
    return ProjectData.model_validate(base | extra)


def test_a_check_passes_at_the_first_try_when_its_first_result_on_that_file_is_not_a_fail() -> None:
    """svg_audit on segno.svg: two FAILs and then PASS, so not at once; on favicon.svg, at once. FAIL is
    the only result that fails: NOT_APPLICABLE and MEASURED pass."""
    report = quality.quality_report("officina", data())
    assert [
        (item.check_name, item.runs, item.failed, item.subjects, item.first_pass) for item in report.checks
    ] == [
        ("svg_audit", 4, 2, 2, 1),
        ("visual_review", 1, 1, 1, 0),
        ("logo_proof", 1, 0, 1, 1),
        ("optical_check", 1, 0, 1, 1),
    ]
    assert (report.subjects, report.first_pass) == (5, 3)


def test_every_failed_check_keeps_its_reason_in_order() -> None:
    failures = quality.quality_report("officina", data()).failures
    assert [(item.at, item.check_name, item.ticket_id, item.phase, item.reason) for item in failures] == [
        (at(1), "svg_audit", "T-0004", "finisher", "3 nodi sottotracciati"),
        (at(3), "svg_audit", "T-0004", "finisher", "ancora 1 nodo"),
        (at(6), "visual_review", "T-0005", "critic", "La coda sparisce a 16 px"),
    ]
    assert failures[0].title == "Titolo T-0004"


def test_tools_say_how_often_they_said_no_and_with_which_words() -> None:
    report = quality.quality_report("officina", data())
    assert [(item.tool, item.uses, item.refused, item.instances) for item in report.tools] == [
        ("deliver", 2, 1, 1),
        ("write_file", 1, 1, 1),
        ("view_image", 3, 0, 2),
    ]
    assert (report.uses, report.refused) == (6, 2)
    assert [
        (item.instance, item.ticket_id, item.role, item.phase, item.turn, item.tool)
        for item in report.refusals
    ] == [
        ("T-0004-a1", "T-0004", "identity-designer", "finisher", 2, "deliver"),
        ("T-0005-a1", "T-0005", "critic", "critic", 2, "write_file"),
    ]
    assert report.refusals[1].message == "un revisore scrive solo in reviews/"


def test_refusals_follow_the_instances_in_the_order_they_started_not_by_name() -> None:
    """Transcripts are read by name: T-0001-a2 comes before T-0005-a1, but it started later."""
    calls = [*CALLS, call(3, 20, "T-0001-a2", "T-0001", "design-director", "design-director")]
    tools = [
        tool(1, "T-0001-a2", 1, "open_ticket", "il pattern non corrisponde a nessun output"),
        *TOOL_CALLS[1:],
    ]
    refusals = quality.quality_report("officina", data(calls=calls, tool_calls=tools)).refusals
    assert [item.instance for item in refusals] == ["T-0004-a1", "T-0005-a1", "T-0001-a2"]


def test_blocked_tickets_and_every_step_back_come_with_their_reason() -> None:
    report = quality.quality_report("officina", data())
    assert report.blocked == 1
    assert [(item.ticket_id, item.action, item.reason) for item in report.setbacks] == [
        ("T-0005", Lifecycle.BLOCK, "Il contratto chiede review/, ma posso scrivere solo in reviews/"),
    ]


def test_a_refusal_in_an_instance_without_calls_still_counts() -> None:
    """A transcript without calls in `usage` does not vanish: the refusal stays, without a role or phase."""
    calls = [tool(1, "T-0009-a1", 1, "render", "render non disponibile")]
    (refusal,) = quality.quality_report("officina", data(tool_calls=calls)).refusals
    assert (refusal.instance, refusal.ticket_id, refusal.role, refusal.phase) == ("T-0009-a1", "", "", "")


def test_a_project_without_checks_or_tools_has_an_empty_report() -> None:
    report = quality.quality_report(
        "fantasma", data(checks=[], tool_calls=[], events=[], tickets=[], calls=[])
    )
    assert (report.checks, report.failures, report.tools, report.refusals, report.setbacks) == (
        [],
        [],
        [],
        [],
        [],
    )
    assert (report.subjects, report.first_pass, report.uses, report.refused, report.blocked) == (
        0,
        0,
        0,
        0,
        0,
    )
