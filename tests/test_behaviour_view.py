"""La vista Modello: come ha lavorato il modello, ruolo per ruolo e turno per turno."""

from __future__ import annotations

from agency.insights import behaviour
from agency.insights.domain import Call, Measures, PhaseSource
from agency.insights.ports import ProjectData


def call(seq: int, minute: int, instance: str, role: str, **extra: object) -> Call:
    base: dict[str, object] = {
        "seq": seq,
        "at": f"2026-11-02T10:{minute:02d}:00+00:00",
        "project": "officina",
        "run": None,
        "ticket_id": instance[:6],
        "ticket_type": "",
        "role": role,
        "instance": instance,
        "phase": role,
        "phase_source": PhaseSource.RECORDED,
        "model": "claude-opus-5-5",
        "effort": None,
        "input_tokens": 100,
        "output_tokens": 10,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_usd": 1.0,
        "stop_reason": "tool_use",
        "request_id": f"req_{seq}",
        "duration_ms": None,
        "ttft_ms": None,
        "reasoning_tokens": None,
        "measures": Measures.MISSING,
    }
    return Call.model_validate(base | extra)


def measured(duration_ms: int, ttft_ms: int, reasoning_tokens: int, effort: str) -> dict[str, object]:
    return {
        "duration_ms": duration_ms,
        "ttft_ms": ttft_ms,
        "reasoning_tokens": reasoning_tokens,
        "effort": effort,
        "measures": Measures.REGISTRY,
    }


CALLS = [
    call(1, 0, "T-0002-a1", "direction-a", cache_read_tokens=900, **measured(4000, 1000, 50, "high")),
    call(2, 1, "T-0002-a1", "direction-a", cache_read_tokens=1900, stop_reason="end_turn"),
    call(3, 2, "T-0001-a1", "design-director", cost_usd=0.5, **measured(2000, 800, 10, "medium")),
    call(
        4,
        3,
        "T-0002-a1",
        "direction-a",
        cache_read_tokens=2900,
        cache_write_5m_tokens=1000,
        stop_reason="max_tokens",
        **measured(8000, 3000, 70, "max"),
    ),
    call(5, 4, "T-0003-a1", "direction-a", **measured(6000, 2000, 30, "high")),
]


def data(calls: list[Call]) -> ProjectData:
    return ProjectData(
        project=None,
        calls=calls,
        tickets=[],
        gates=[],
        concepts=[],
        judgments=[],
        events=[],
        checks=[],
        tool_calls=[],
        runs=[],
    )


def test_each_role_says_how_much_context_it_read_and_how_the_model_answered() -> None:
    """direction-a: 4 chiamate con contesti di 1000, 2000, 4000 e 100. Le misure: solo 3 chiamate."""
    report = behaviour.behaviour_report("officina", data(CALLS))
    assert [(role.role, role.calls, role.instances, role.cost_usd) for role in report.roles] == [
        ("direction-a", 4, 2, 4.0),
        ("design-director", 1, 1, 0.5),
    ]
    role = report.roles[0]
    assert (role.mean_context, role.max_context, role.output_tokens) == (1775.0, 4000, 40)
    assert role.cache_hit == 5700 / 7100
    assert (role.measured, role.mean_duration_ms, role.median_ttft_ms, role.reasoning_tokens) == (
        3,
        6000.0,
        2000,
        150,
    )
    assert role.efforts == ["high", "max"]
    assert [(item.reason, item.calls) for item in role.stop_reasons] == [
        ("tool_use", 2),
        ("end_turn", 1),
        ("max_tokens", 1),
    ]


def test_each_instance_is_a_series_of_turns_in_order() -> None:
    report = behaviour.behaviour_report("officina", data(CALLS))
    assert [(item.instance, item.role, len(item.turns)) for item in report.instances] == [
        ("T-0002-a1", "direction-a", 3),
        ("T-0001-a1", "design-director", 1),
        ("T-0003-a1", "direction-a", 1),
    ]
    first = report.instances[0]
    assert [(turn.seq, turn.context, turn.cache_read_tokens, turn.stop_reason) for turn in first.turns] == [
        (1, 1000, 900, "tool_use"),
        (2, 2000, 1900, "end_turn"),
        (4, 4000, 2900, "max_tokens"),
    ]
    assert (first.turns[1].duration_ms, first.turns[1].ttft_ms, first.turns[1].reasoning_tokens) == (
        None,
        None,
        None,
    )
    assert (first.peak_context, first.cache_hit) == (4000, 5700 / 7000)


def test_the_project_counts_every_stop_reason_and_says_which_answers_were_cut() -> None:
    """max_tokens: il ciclo dell'agente non mette la risposta in cronologia e la richiede."""
    report = behaviour.behaviour_report("officina", data(CALLS))
    assert [(item.reason, item.calls, item.complete) for item in report.stop_reasons] == [
        ("tool_use", 3, True),
        ("end_turn", 1, True),
        ("max_tokens", 1, False),
    ]


def test_a_project_without_calls_has_no_behaviour() -> None:
    report = behaviour.behaviour_report("fantasma", data([]))
    assert (report.roles, report.instances, report.stop_reasons) == ([], [], [])
