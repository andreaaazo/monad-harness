"""Prices in dollars per million tokens, from the API reference of 2026-10-06."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    """Dollars per million tokens of each kind; `_price` derives the cache rates from the input rate."""

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
    # Possible targets of the server-side fallbacks.
    "claude-opus-5": _price(5.0, 25.0, 0.50),
    "claude-opus-4-8": _price(5.0, 25.0, 0.50),
    "claude-sonnet-5": _price(2.0, 10.0, 0.20),
}
# An unknown model is priced high: better to stop early than to find out from the invoice.
UNKNOWN_MODEL = _price(10.0, 50.0, 1.0)


def price_of(model: str) -> Price:
    """The model's prices, or `UNKNOWN_MODEL`'s for a model not in `PRICES`."""
    return PRICES.get(model, UNKNOWN_MODEL)


def cost_usd(model: str, usage: dict) -> float:
    """The cost of one billed attempt. Without the cache-write breakdown, every write is a 5-minute one."""
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


def call_cost_usd(model: str, usage: dict, requested_model: str) -> float:
    """Cost of one call; `usage.iterations`, when present, lists every attempt the call was billed for.

    Each attempt is priced at its own model's rates; an entry without a model is priced at the requested one.
    """
    iterations = usage.get("iterations")
    if not iterations:
        return cost_usd(model, usage)
    return sum(cost_usd(attempt.get("model") or requested_model, attempt) for attempt in iterations)
