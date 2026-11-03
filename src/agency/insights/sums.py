"""I conti sulle chiamate che più viste condividono: uno solo, così Run, Fasi e Modello non divergono.

Le medie di durata e TTFT valgono solo sulle chiamate misurate: una chiamata senza misure non vale zero.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable
from datetime import datetime

from agency.insights.domain import Call, Measures


def context(call: Call) -> int:
    """I token che il modello ha letto in quella chiamata: ingresso, cache letta e cache scritta."""
    return (
        call.input_tokens + call.cache_read_tokens + call.cache_write_5m_tokens + call.cache_write_1h_tokens
    )


def groups[T](items: Iterable[T], key: Callable[[T], str]) -> dict[str, list[T]]:
    """Gli elementi per chiave, nell'ordine in cui la chiave compare la prima volta."""
    grouped: dict[str, list[T]] = {}
    for item in items:
        grouped.setdefault(key(item), []).append(item)
    return grouped


def cost(calls: Iterable[Call]) -> float:
    return sum(call.cost_usd for call in calls)


def minutes(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60


def measured(calls: Iterable[Call]) -> list[Call]:
    return [call for call in calls if call.measures is not Measures.MISSING]


def mean_duration_ms(calls: Iterable[Call]) -> float | None:
    durations = [call.duration_ms for call in measured(calls) if call.duration_ms is not None]
    return statistics.fmean(durations) if durations else None


def median_ttft_ms(calls: Iterable[Call]) -> int | None:
    ttft = [call.ttft_ms for call in measured(calls) if call.ttft_ms is not None]
    return statistics.median_low(ttft) if ttft else None


def reasoning_tokens(calls: Iterable[Call]) -> int:
    return sum(call.reasoning_tokens or 0 for call in measured(calls))


def model_ms(calls: Iterable[Call]) -> int | None:
    """Il tempo passato col modello, sulle chiamate misurate; None se nessuna lo è."""
    durations = [call.duration_ms for call in measured(calls) if call.duration_ms is not None]
    return sum(durations) if durations else None
