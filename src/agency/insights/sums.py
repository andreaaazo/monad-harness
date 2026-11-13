"""The sums on calls that several views share: one of each, so the run, phases and model views agree.

The duration and TTFT averages count only the measured calls: a call without measures is not a zero.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable
from datetime import datetime

from agency.insights.domain import Call, Measures


def context(call: Call) -> int:
    """The tokens the model read in that call: input, cache reads and cache writes."""
    return (
        call.input_tokens + call.cache_read_tokens + call.cache_write_5m_tokens + call.cache_write_1h_tokens
    )


def groups[T](items: Iterable[T], key: Callable[[T], str]) -> dict[str, list[T]]:
    """The items by key, in the order each key first appears."""
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
    """The time spent with the model, over the measured calls; None if none is measured."""
    durations = [call.duration_ms for call in measured(calls) if call.duration_ms is not None]
    return sum(durations) if durations else None
