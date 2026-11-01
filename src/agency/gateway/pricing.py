"""Prezzi in dollari per milione di token, dal riferimento API del 2026-10-06."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write_5m: float
    cache_write_1h: float


def _price(input_: float, output: float, read: float) -> Price:
    return Price(input_, output, read, input_ * 1.25, input_ * 2)


PRICES: dict[str, Price] = {
    "claude-opus-5-5": _price(4.0, 20.0, 0.20),
    "claude-sonnet-5-5": _price(2.0, 10.0, 0.20),
    # Possibili destinazioni dei fallback lato server.
    "claude-opus-5": _price(5.0, 25.0, 0.50),
    "claude-opus-4-8": _price(5.0, 25.0, 0.50),
    "claude-sonnet-5": _price(2.0, 10.0, 0.20),
}
# Per un modello sconosciuto si stima per eccesso: meglio fermarsi prima che scoprirlo sulla fattura.
UNKNOWN_MODEL = _price(10.0, 50.0, 1.0)


def price_of(model: str) -> Price:
    return PRICES.get(model, UNKNOWN_MODEL)


def cost_usd(model: str, usage: dict) -> float:
    price = price_of(model)
    breakdown = usage.get("cache_creation") or {}
    write_5m = breakdown.get("ephemeral_5m_input_tokens")
    write_1h = breakdown.get("ephemeral_1h_input_tokens", 0) or 0
    if write_5m is None:
        write_5m = usage.get("cache_creation_input_tokens", 0) or 0
    return (
        (usage.get("input_tokens", 0) or 0) * price.input
        + (usage.get("output_tokens", 0) or 0) * price.output
        + (usage.get("cache_read_input_tokens", 0) or 0) * price.cache_read
        + write_5m * price.cache_write_5m
        + write_1h * price.cache_write_1h
    ) / 1_000_000
