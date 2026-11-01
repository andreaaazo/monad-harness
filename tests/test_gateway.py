from pathlib import Path

import pytest

from agency.config import Settings
from agency.gateway import BudgetExceeded, CallContext, ModelGateway, ModelRequest, ScriptedTransport
from agency.gateway.pricing import cost_usd
from agency.ledger import Ledger

CONTEXT = CallContext(project="p", ticket_id="T-0001", role="critic", instance="i1")


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


def gateway(tmp_path: Path, transport: ScriptedTransport, **limits: float) -> ModelGateway:
    settings = Settings(data_dir=tmp_path, _env_file=None, **limits)  # type: ignore[call-arg]
    return ModelGateway(transport, Ledger(settings.ledger_path), settings)


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
