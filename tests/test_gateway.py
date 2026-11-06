import json
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
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
    ModelResponse,
    ScriptedTransport,
    Transport,
)
from agency.gateway.pricing import PRICES, cost_usd
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
    tmp_path: Path,
    transport: Transport,
    clock: Callable[[], float] = time.monotonic,
    budget: float | None = 25.0,
) -> ModelGateway:
    """Il progetto `p` di CONTEXT, con il tetto che il cliente ha dichiarato. None: nessun tetto."""
    settings = Settings(data_dir=tmp_path, _env_file=None)  # type: ignore[call-arg]
    ledger = Ledger(settings.ledger_path)
    if budget is not None:
        ledger.set_project(CONTEXT.project, budget)
    return ModelGateway(transport, ledger, settings, clock=clock)


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


def test_a_fallback_call_is_charged_only_for_the_serving_attempt(tmp_path: Path) -> None:
    """Shaped like the claude-api reference: opus-5-5 declines mid-stream and opus-5 serves the answer.

    `usage.iterations` holds both attempts; the top-level `usage` covers only the one that served.
    """
    declined = {
        "type": "message",
        "model": "claude-opus-5-5",
        "input_tokens": 50_000,
        "output_tokens": 6_000,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    served = declined | {"type": "fallback_message", "model": "claude-opus-5", "output_tokens": 3_000}
    answer = {
        "content": [
            {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-5"}},
            {"type": "text", "text": "ok"},
        ],
        "stop_reason": "end_turn",
        "model": "claude-opus-5",
        "usage": {
            "input_tokens": 50_000,
            "output_tokens": 3_000,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "iterations": [declined, served],
        },
    }
    gw = gateway(tmp_path, ScriptedTransport([answer]))

    response = gw.call(CONTEXT, request())

    serving_attempt = cost_usd("claude-opus-5", {"input_tokens": 50_000, "output_tokens": 3_000})
    assert serving_attempt == pytest.approx(0.325)
    # Pins current behavior of COR-008; phase 2 (Task 2.13) flips this assertion to both attempts, 0.645 $.
    assert response.cost_usd == pytest.approx(serving_attempt)
    assert gw.ledger.spent("p") == pytest.approx(serving_attempt)


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


def test_live_transport_sends_the_gateway_params_through_the_sdk(tmp_path: Path) -> None:
    """The real SDK builds both requests and httpx2.MockTransport answers them: nothing leaves the machine."""
    seen: list[httpx2.Request] = []

    def answer(sent: httpx2.Request) -> httpx2.Response:
        seen.append(sent)
        if sent.url.path == "/v1/messages/count_tokens":
            return httpx2.Response(200, json={"input_tokens": 1000})
        stream = b"".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n".encode() for e in SSE)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=stream)

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(answer))
    client = anthropic.Anthropic(api_key="chiave-finta", http_client=http, max_retries=0)
    gw = gateway(tmp_path, AnthropicTransport(client=client))
    with_tools = request()
    with_tools.tools = [{"name": "consegna", "description": "d", "input_schema": {"type": "object"}}]

    gw.call(CONTEXT, request())
    gw.call(CONTEXT, with_tools)

    assert [sent.url.path for sent in seen] == ["/v1/messages/count_tokens", "/v1/messages"] * 2
    counted = [json.loads(sent.content) for sent in seen[0::2]]
    assert [set(body) for body in counted] == [
        {"model", "system", "messages"},
        {"model", "system", "tools", "messages"},
    ]
    streamed = seen[3]
    body = json.loads(streamed.content)
    assert set(body) == {
        "model",
        "max_tokens",
        "system",
        "messages",
        "tools",
        "thinking",
        "output_config",
        "cache_control",
        "fallbacks",
        "stream",
    }
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "high"}
    assert body["cache_control"] == {"type": "ephemeral"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in streamed.headers["anthropic-beta"].split(",")


def test_estimate_after_the_first_call_prices_context_and_new_tokens(tmp_path: Path) -> None:
    """The context is re-read from the cache; only the last message is new. An image counts 2,500 tokens."""
    context = {"input_tokens": 1_000, "cache_read_input_tokens": 90_000, "cache_creation_input_tokens": 9_000}
    previous = ModelResponse(
        content=[],
        stop_reason="tool_use",
        stop_details=None,
        usage=context,
        model="claude-opus-5-5",
        cost_usd=0.0,
        request_id="",
    )
    image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A" * 30_000}}
    text = {"type": "text", "text": "x" * 3_000}
    result = {"type": "tool_result", "tool_use_id": "t1", "content": [text, image]}
    follow_up = request()
    follow_up.messages = [{"role": "user", "content": [result]}]
    gw = gateway(tmp_path, ScriptedTransport([]))

    estimate = gw.estimate_usd(follow_up, previous)

    price = PRICES["claude-opus-5-5"]
    fresh = 1_000 + 2_500
    expected = (100_000 * price.cache_read + fresh * price.cache_write_5m + 4_000 * price.output) / 1e6
    assert estimate == pytest.approx(expected)


def test_a_cap_crossed_only_by_the_input_part_stops_the_call(tmp_path: Path) -> None:
    """The follow-up's expected output alone fits the cap; its 100,000 context tokens push it over."""
    first = reply(input_tokens=1_000, output=100, read=90_000, write=9_000)
    transport = ScriptedTransport([first, reply()])
    gw = gateway(tmp_path, transport, budget=0.16)
    previous = gw.call(CONTEXT, request())
    assert previous.context_tokens == 100_000
    output_part = 4_000 * PRICES["claude-opus-5-5"].output / 1e6
    assert gw.ledger.spent("p") + output_part <= 0.16  # without the input part the call would go out

    with pytest.raises(BudgetExceeded, match="spesi"):
        gw.call(CONTEXT, request(), previous)
    assert len(transport.requests) == 1


def test_parallel_calls_cannot_overspend_the_cap(tmp_path: Path) -> None:
    """Five calls at once against a 0.20 $ cap, each costing exactly its 0.085 $ estimate.

    The five threads leave a barrier together. A call that passes the check waits inside `stream` until all
    five have been decided, so no usage is recorded while the others are checked: only the estimates of the
    calls in flight can stop them. Two fit in the cap and three are refused, in whatever order the threads
    run.
    """
    calls = 5
    start = threading.Barrier(calls, timeout=10)  # the timeouts here only guard against a hang
    decided = threading.Semaphore(0)
    release = threading.Event()

    class HeldInFlight(ScriptedTransport):
        def stream(self, params: dict) -> dict:
            decided.release()
            assert release.wait(timeout=10)
            return super().stream(params)

    transport = HeldInFlight([reply(input_tokens=0, output=4_000, write=1_000) for _ in range(calls)])
    gw = gateway(tmp_path, transport, budget=0.20)
    assert gw.estimate_usd(request(), None) == pytest.approx(0.085)

    def one_call() -> ModelResponse | BudgetExceeded:
        start.wait()
        try:
            return gw.call(CONTEXT, request())
        except BudgetExceeded as refused:
            decided.release()
            return refused

    with ThreadPoolExecutor(calls) as pool:
        futures = [pool.submit(one_call) for _ in range(calls)]
        for _ in range(calls):
            assert decided.acquire(timeout=10)
        release.set()
        outcomes = [future.result() for future in futures]

    streamed = [outcome for outcome in outcomes if isinstance(outcome, ModelResponse)]
    refused = [outcome for outcome in outcomes if isinstance(outcome, BudgetExceeded)]
    assert len(transport.requests) == 2
    assert (len(streamed), len(refused)) == (2, 3)
    assert [response.cost_usd for response in streamed] == pytest.approx([0.085, 0.085])
    assert gw.ledger.spent("p") <= 0.20
    assert gw.ledger.spent("p") == pytest.approx(0.17)


def test_a_call_that_fails_while_streaming_releases_its_reservation(tmp_path: Path) -> None:
    """The first call reserves its 0.085 $ estimate, then the connection drops while it streams.

    It spent nothing, so under a 0.20 $ cap two more calls still fit, one after the other.
    """

    class DropsFirst(ScriptedTransport):
        drops = 1

        def stream(self, params: dict) -> dict:
            if self.drops:
                self.drops -= 1
                dropped = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
                raise anthropic.APIConnectionError(request=dropped)
            return super().stream(params)

    transport = DropsFirst([reply(input_tokens=0, output=4_000, write=1_000) for _ in range(2)])
    gw = gateway(tmp_path, transport, budget=0.20)
    assert gw.estimate_usd(request(), None) == pytest.approx(0.085)
    with pytest.raises(anthropic.APIConnectionError):
        gw.call(CONTEXT, request())
    assert gw.ledger.spent("p") == 0

    gw.call(CONTEXT, request())
    gw.call(CONTEXT, request())

    assert len(transport.requests) == 2
    assert gw.ledger.spent("p") == pytest.approx(0.17)


def test_project_ceiling_stops_before_the_call(tmp_path: Path) -> None:
    transport = ScriptedTransport([reply()])
    gw = gateway(tmp_path, transport, budget=0.01)
    with pytest.raises(BudgetExceeded, match="spesi"):
        gw.call(CONTEXT, request())
    assert transport.requests == []


def test_project_ceiling_counts_previous_spend(tmp_path: Path) -> None:
    transport = ScriptedTransport([reply(output=10_000), reply()])
    gw = gateway(tmp_path, transport, budget=0.25)
    previous = gw.call(CONTEXT, request())
    with pytest.raises(BudgetExceeded, match="spesi"):
        gw.call(CONTEXT, request(), previous)
    assert len(transport.requests) == 1


def test_a_project_without_a_declared_budget_spends_nothing(tmp_path: Path) -> None:
    """Prima valeva il tetto delle impostazioni: ora senza un tetto dichiarato non parte nulla (ADR-0043)."""
    counted: list[dict] = []

    class Counting(ScriptedTransport):
        def count_tokens(self, params: dict) -> int:
            counted.append(params)
            return super().count_tokens(params)

    transport = Counting([reply()])
    gw = gateway(tmp_path, transport, budget=None)
    with pytest.raises(BudgetExceeded, match="p non ha un tetto dichiarato"):
        gw.call(CONTEXT, request())
    assert transport.requests == [] and counted == []  # niente esce, nemmeno per contare i token


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
