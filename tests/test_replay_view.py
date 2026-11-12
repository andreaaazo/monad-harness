"""The replay view: an instance turn by turn, with each call's measures and the discarded answers."""

from __future__ import annotations

from agency.insights import replay
from agency.insights.domain import AssistantTurn, Call, Measures, PhaseSource, TranscriptRecord


def call(seq: int, request_id: str, stop_reason: str = "tool_use", cost: float = 1.0) -> Call:
    return Call(
        seq=seq,
        at=f"2026-11-02T10:{seq:02d}:00+00:00",
        project="merlo4",
        run=1,
        ticket_id="T-0002",
        ticket_type="schizzo",
        role="direction-a",
        instance="T-0002-a1",
        phase="explorer",
        phase_source=PhaseSource.RECORDED,
        model="claude-opus-5-5",
        effort="high",
        input_tokens=100,
        output_tokens=10,
        cache_read_tokens=900 * seq,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        cost_usd=cost,
        stop_reason=stop_reason,
        request_id=request_id,
        duration_ms=4000,
        ttft_ms=1000,
        reasoning_tokens=20,
        measures=Measures.REGISTRY,
    )


def turn(request_id: str | None, text: str) -> AssistantTurn:
    return AssistantTurn(
        request_id=request_id, thinking=[], hidden_thinking=0, text=[text], tools=[], notes=[]
    )


def record(*turns: AssistantTurn) -> TranscriptRecord:
    return TranscriptRecord(
        project="merlo4",
        instance="T-0002-a1",
        task="il compito",
        turns=list(turns),
        outcome_state="delivered",
        outcome_note="",
        images=3,
        unreadable=0,
    )


def test_turns_meet_their_calls_by_request_and_a_discarded_answer_sits_where_it_happened() -> None:
    """The cut-off answer (#2) does not go into the transcript: it shows before the turn that redoes it."""
    calls = [call(1, "req_1"), call(2, "req_x", "max_tokens"), call(3, "req_2", "end_turn")]
    report = replay.replay_report(record(turn("req_1", "uno"), turn("req_2", "due")), calls)
    assert report.alignment is replay.Alignment.BY_REQUEST
    first, second = report.turns
    assert (first.number, first.measured and first.measured.seq, first.discarded) == (1, 1, [])
    assert (second.measured and second.measured.seq, [item.seq for item in second.discarded]) == (3, [2])
    assert second.discarded[0].stop_reason == "max_tokens"
    assert (first.measured and first.measured.context) == 1000


def test_old_transcripts_meet_their_calls_by_order_once_the_discarded_answers_are_set_aside() -> None:
    calls = [call(1, "req_1"), call(2, "req_x", "max_tokens"), call(3, "req_2", "end_turn")]
    report = replay.replay_report(record(turn(None, "uno"), turn(None, "due")), calls)
    assert report.alignment is replay.Alignment.BY_ORDER
    assert [
        (item.measured and item.measured.seq, [d.seq for d in item.discarded]) for item in report.turns
    ] == [
        (1, []),
        (3, [2]),
    ]


def test_when_the_order_does_not_add_up_no_turn_gets_somebody_elses_measures() -> None:
    calls = [call(1, "req_1"), call(2, "req_2"), call(3, "req_3")]
    report = replay.replay_report(record(turn(None, "uno"), turn(None, "due")), calls)
    assert report.alignment is replay.Alignment.NONE
    assert [(item.measured, item.discarded) for item in report.turns] == [(None, []), (None, [])]
    assert report.trailing_discarded == []


def test_a_refusal_after_the_last_turn_closes_the_replay() -> None:
    """A model refusal blocks the ticket: its call has no turn after it."""
    calls = [call(1, "req_1"), call(2, "req_x", "refusal")]
    report = replay.replay_report(record(turn("req_1", "uno")), calls)
    assert [item.seq for item in report.trailing_discarded] == [2]


def test_the_replay_says_who_worked_what_it_cost_and_how_it_ended() -> None:
    calls = [call(1, "req_1", cost=0.5), call(2, "req_2", cost=0.25)]
    report = replay.replay_report(record(turn("req_1", "uno"), turn("req_2", "due")), calls)
    assert (report.ticket_id, report.role, report.phase, report.calls, report.cost_usd) == (
        "T-0002",
        "direction-a",
        "explorer",
        2,
        0.75,
    )
    assert (report.task, report.outcome_state, report.images, report.turns[1].text) == (
        "il compito",
        "delivered",
        3,
        ["due"],
    )


def test_a_transcript_without_calls_still_replays_without_measures() -> None:
    report = replay.replay_report(record(turn(None, "uno")), [])
    assert (report.alignment, report.ticket_id, report.calls, report.turns[0].measured) == (
        replay.Alignment.NONE,
        "",
        0,
        None,
    )
