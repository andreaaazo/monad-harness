"""The read slice's rules: the phase and the measures of a call, and what the traces say."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency.contracts import phase
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.domain import (
    Measures,
    PhaseSource,
    TraceMeasure,
    derive_phase,
    project_calls,
)
from support.insights import TICKETS, call, span, usage

TRACE = TraceMeasure(request_id="req_1", duration_ms=8200, ttft_ms=1400, effort="high", reasoning_tokens=310)


# The rules: the phase


@pytest.mark.parametrize(
    ("instance", "ticket", "role", "expected"),
    [
        ("T-0001-a1-plan", "T-0001", "design-director", "director-plan"),
        ("T-0001-a2-select", "T-0001", "design-director", "director-select"),
        ("T-0001-a1-present", "T-0001", "design-director", "director-present"),
        ("T-0001-a3", "T-0001", "design-director", "design-director"),
        ("T-0002-a1", "T-0002", "direction-a", "explorer"),
        ("T-0009-a1", "T-0009", "critic", "critic"),
        ("T-0099-a1", "T-0099", "critic", "critic"),  # a ticket the registry lacks: the role stays
    ],
)
def test_phase_of_an_old_call_is_derived_with_the_rule_the_engine_uses(
    instance: str, ticket: str, role: str, expected: str
) -> None:
    assert derive_phase(usage(instance=instance, ticket_id=ticket, role=role), TICKETS) == expected


def test_a_recorded_phase_wins_over_the_derived_one() -> None:
    """The recorded phase is the truth of its time, even if today's rule would say otherwise."""
    (call,) = project_calls([usage(phase="explorer-idea")], TICKETS, {})
    assert (call.phase, call.phase_source) == ("explorer-idea", PhaseSource.RECORDED)
    (old,) = project_calls([usage()], TICKETS, {})
    assert (old.phase, old.phase_source) == ("director-plan", PhaseSource.DERIVED)


def test_instance_names_are_written_and_read_by_one_rule() -> None:
    for mode in (None, *phase.MODES):
        assert phase.mode_of(phase.instance("T-0042", 3, mode)) == mode
    assert phase.mode_of("i1") is None  # a test name is not an engine instance


# The rules: the measures


def test_a_new_call_keeps_its_own_measures_even_if_a_trace_exists() -> None:
    new = usage(effort="medium", duration_ms=5000, ttft_ms=None, reasoning_tokens=12)
    (call,) = project_calls([new], TICKETS, {"req_1": TRACE})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == ("medium", 5000, None, 12, Measures.REGISTRY)


def test_an_old_call_takes_its_measures_from_the_trace() -> None:
    (call,) = project_calls([usage()], TICKETS, {"req_1": TRACE})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == ("high", 8200, 1400, 310, Measures.TRACES)


def test_an_old_call_without_trace_says_it_was_not_measured() -> None:
    (call,) = project_calls([usage()], TICKETS, {})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == (None, None, None, None, Measures.MISSING)


def test_a_call_keeps_cost_tokens_and_the_type_of_its_ticket() -> None:
    (call,) = project_calls(
        [usage(ticket_id="T-0002", instance="T-0002-a1", role="direction-a")], TICKETS, {}
    )
    assert (call.ticket_type, call.cost_usd, call.input_tokens, call.request_id) == (
        "schizzo",
        0.01,
        100,
        "req_1",
    )
    (orphan,) = project_calls([usage(ticket_id="T-0099")], TICKETS, {})
    assert orphan.ticket_type == ""


def test_traces_give_duration_ttft_effort_and_reasoning_by_request(tmp_path: Path) -> None:
    lines = [
        span(
            "anthropic.messages.create",
            "req_1",
            **{
                "gen_ai.response.time_to_first_chunk": 1.4004,
                "gen_ai.request.reasoning.level": "high",
                "gen_ai.usage.reasoning.output_tokens": 310,
            },
        ),
        span("model.call", "req_9"),  # our own traces lack the SDK's measures
        '{"name": "anthropic.messages.create", "start": 1, ',  # a line cut short by a killed process
        span("anthropic.messages.create", "req_2"),
    ]
    path = tmp_path / "traces.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    reading = JsonlTraces(path).read()

    assert reading.measures["req_1"] == TRACE
    assert reading.measures["req_2"] == TraceMeasure(
        request_id="req_2", duration_ms=8200, ttft_ms=None, effort=None, reasoning_tokens=None
    )
    assert set(reading.measures) == {"req_1", "req_2"}
    assert reading.unreadable == 1


def test_a_stray_non_utf8_byte_costs_one_line_not_the_whole_trace_file(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    path.write_bytes(
        span("anthropic.messages.create", "req_1").encode()
        + b"\n"
        + b'{"name": "\xff"}\n'
        + span("anthropic.messages.create", "req_2").encode()
        + b"\n"
    )

    reading = JsonlTraces(path).read()

    assert set(reading.measures) == {"req_1", "req_2"}
    assert reading.unreadable == 1


def test_a_broken_stream_is_not_a_complete_answer() -> None:
    from agency.insights import behaviour

    stops = behaviour._stops([call(1), call(2)])
    assert [(stop.reason, stop.complete) for stop in stops] == [("tool_use", True)]
    (projected,) = project_calls(
        [usage(seq=3, request_id="req_3", stop_reason="malformed_stream")], TICKETS, {}
    )
    (broken,) = behaviour._stops([projected])
    assert (broken.reason, broken.complete) == ("malformed_stream", False)


def test_missing_traces_are_not_an_error(tmp_path: Path) -> None:
    reading = JsonlTraces(tmp_path / "traces.jsonl").read()
    assert (reading.measures, reading.unreadable) == ({}, 0)
