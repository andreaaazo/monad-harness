import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import anthropic
import httpx2
import pytest

from agency.config import Settings
from agency.contracts.run import RunCommand
from agency.gateway import (
    AnthropicTransport,
    BudgetExceeded,
    CallContext,
    ModelGateway,
    ModelRequest,
    ScriptedTransport,
)
from agency.gateway.pricing import cost_usd
from agency.ledger import Ledger
from agency.telemetry import fingerprint

CONTEXT = CallContext(project="p", ticket_id="T-0001", role="critic", instance="i1", phase="critic-board")


def reply(input_tokens: int = 100, output: int = 50, read: int = 0, write: int = 0) -> dict:
    return {
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "model": "claude-opus-5-5",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output,
            "cache_read_input_tokens": read,
            "cache_creation_input_tokens": write,
        },
    }


def request() -> ModelRequest:
    return ModelRequest(
        model="claude-opus-5-5",
        effort="high",
        system=[{"type": "text", "text": "sistema"}],
        messages=[{"role": "user", "content": "ciao"}],
    )


def gateway(
    tmp_path: Path, transport: ScriptedTransport, clock: Callable[[], float] = time.monotonic, **limits: float
) -> ModelGateway:
    settings = Settings(data_dir=tmp_path, _env_file=None, **limits)  # type: ignore[call-arg]
    return ModelGateway(transport, Ledger(settings.ledger_path), settings, clock=clock)


def test_cost_counts_cache_at_its_own_price() -> None:
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation": {"ephemeral_5m_input_tokens": 1_000_000, "ephemeral_1h_input_tokens": 1_000_000},
    }
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx(4 + 20 + 0.2 + 5 + 8)


def test_unknown_model_is_priced_high() -> None:
    assert cost_usd("modello-nuovo", {"output_tokens": 1_000_000}) == pytest.approx(50)


def test_call_records_usage_and_request_shape(tmp_path: Path) -> None:
    transport = ScriptedTransport([reply(write=2000)])
    gw = gateway(tmp_path, transport)
    response = gw.call(CONTEXT, request())
    assert response.stop_reason == "end_turn"
    assert gw.ledger.spent("p") == pytest.approx(response.cost_usd)
    sent = transport.requests[0]
    assert sent["thinking"] == {"type": "adaptive"}
    assert sent["output_config"] == {"effort": "high"}
    assert sent["cache_control"] == {"type": "ephemeral"}
    for forbidden in ("temperature", "top_p", "tool_choice", "budget_tokens"):
        assert forbidden not in sent


class Slow(ScriptedTransport):
    """Una risposta che arriva dopo 2,5 secondi di un orologio finto."""

    def __init__(self, responses: list[dict], now: list[float]) -> None:
        super().__init__(responses)
        self.now = now

    def stream(self, params: dict) -> dict:
        self.now[0] += 2.5
        return super().stream(params)


def test_call_records_phase_effort_duration_ttft_and_reasoning(tmp_path: Path) -> None:
    answer = reply() | {"_ttft_ms": 400}
    answer["usage"] = reply()["usage"] | {"output_tokens_details": {"thinking_tokens": 30}}
    now = [10.0]
    gw = gateway(tmp_path, Slow([answer], now), clock=lambda: now[0])

    gw.call(CONTEXT, request())

    (row,) = gw.ledger.usage("p")
    assert (row.phase, row.effort, row.duration_ms, row.ttft_ms, row.reasoning_tokens) == (
        "critic-board",
        "high",
        2500,
        400,
        30,
    )
    assert row.run is None


def test_what_was_not_measured_stays_empty_not_zero(tmp_path: Path) -> None:
    gw = gateway(tmp_path, ScriptedTransport([reply()]))
    gw.call(CONTEXT, request())
    (row,) = gw.ledger.usage("p")
    assert (row.ttft_ms, row.reasoning_tokens) == (None, None)
    assert row.duration_ms is not None and row.duration_ms >= 0


def test_calls_belong_to_the_run_the_session_started(tmp_path: Path) -> None:
    gw = gateway(tmp_path, ScriptedTransport([reply(), reply()]))
    taken = fingerprint.take(Settings(_env_file=None), "", "", tools=())  # type: ignore[call-arg]
    first = gw.ledger.record_run("p", RunCommand.RUN, taken)
    gw.belongs_to(first)
    gw.call(CONTEXT, request())
    second = gw.ledger.record_run("p", RunCommand.RESUME, taken)
    gw.belongs_to(second)
    gw.call(CONTEXT, request())
    assert [row.run for row in gw.ledger.usage("p")] == [first, second]


SSE = [
    {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant",
     "model": "claude-opus-5-5", "content": [], "stop_reason": None, "stop_sequence": None,
     "usage": {"input_tokens": 10, "output_tokens": 1}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Ciao"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " a tutti"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
     "usage": {"output_tokens": 40, "output_tokens_details": {"thinking_tokens": 25}}},
    {"type": "message_stop"},
]  # fmt: skip


def test_anthropic_transport_measures_the_first_chunk_without_calling_the_api() -> None:
    """Lo stream arriva un evento alla volta e l'orologio avanza con lui: il testo arriva dopo 500 ms."""
    now = [100.0]
    arrives = {"message_start": 0.1, "content_block_delta": 0.4}

    def events() -> Iterator[bytes]:
        for event in SSE:
            now[0] += arrives.get(event["type"], 0.0)
            arrives.pop(event["type"], None)
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()

    def answer(_: httpx2.Request) -> httpx2.Response:
        headers = {"content-type": "text/event-stream", "request-id": "req_prova"}
        return httpx2.Response(200, headers=headers, content=events())

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(answer))
    client = anthropic.Anthropic(api_key="chiave-finta", http_client=http, max_retries=0)
    transport = AnthropicTransport(client=client, clock=lambda: now[0])

    data = transport.stream({"model": "claude-opus-5-5", "max_tokens": 64, "messages": []})

    assert data["_ttft_ms"] == 500
    assert data["_request_id"] == "req_prova"
    assert data["content"][0]["text"] == "Ciao a tutti"
    assert data["usage"]["output_tokens_details"] == {"thinking_tokens": 25}


def test_project_ceiling_stops_before_the_call(tmp_path: Path) -> None:
    transport = ScriptedTransport([reply()])
    gw = gateway(tmp_path, transport, project_budget_usd=0.01)
    with pytest.raises(BudgetExceeded, match="spesi"):
        gw.call(CONTEXT, request())
    assert transport.requests == []


def test_project_ceiling_counts_previous_spend(tmp_path: Path) -> None:
    transport = ScriptedTransport([reply(output=10_000), reply()])
    gw = gateway(tmp_path, transport, project_budget_usd=0.25)
    previous = gw.call(CONTEXT, request())
    with pytest.raises(BudgetExceeded, match="spesi"):
        gw.call(CONTEXT, request(), previous)
    assert len(transport.requests) == 1


def test_budget_chosen_for_the_project_wins(tmp_path: Path) -> None:
    gw = gateway(tmp_path, ScriptedTransport([]))
    gw.ledger.set_project("p", 0.01)
    with pytest.raises(BudgetExceeded):
        gw.call(CONTEXT, request())


def test_malformed_tool_json_is_retried(tmp_path: Path) -> None:
    class Flaky(ScriptedTransport):
        fails = 1

        def stream(self, params: dict) -> dict:
            if self.fails:
                self.fails -= 1
                raise ValueError("JSON illeggibile")
            return super().stream(params)

    assert gateway(tmp_path, Flaky([reply()])).call(CONTEXT, request()).stop_reason == "end_turn"


def test_key_reaches_settings_from_the_documented_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.anthropic_api_key is not None
    assert "sk-ant-test" not in repr(settings)
