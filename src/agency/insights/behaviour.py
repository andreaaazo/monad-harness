"""La vista Modello: come ha lavorato il modello, ruolo per ruolo e turno per turno.

Il contesto di un turno è ciò che il modello ha letto in quella chiamata: ingresso, cache letta e cache
scritta. Durata, TTFT, ragionamento ed effort valgono solo sulle chiamate misurate: una chiamata di prima di
M1.6 senza traccia non vale zero, non c'è.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from agency.insights import sums
from agency.insights.domain import Call
from agency.insights.ports import ProjectData

# Le risposte che non arrivano intere. Il ciclo dell'agente (agents/loop.py) non mette in cronologia una
# risposta troncata e la richiede con un limite più alto; dopo un rifiuto blocca il ticket. Anche un flusso
# interrotto (`malformed_stream`, registrato dal gateway) non è una risposta intera.
INCOMPLETE = frozenset({"max_tokens", "refusal", "model_context_window_exceeded", "malformed_stream"})


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StopCount(_View):
    """Why the model stopped writing, and how often. `complete`: the answer arrived whole."""

    reason: str
    calls: int
    complete: bool


class RoleBehaviour(_View):
    """A role: how much context it read, how much of it came from the cache, how much it thought and
    waited."""

    role: str
    calls: int
    instances: int
    cost_usd: float
    mean_context: float
    max_context: int
    cache_hit: float
    output_tokens: int
    measured: int
    reasoning_tokens: int
    mean_duration_ms: float | None
    median_ttft_ms: int | None
    efforts: list[str]
    stop_reasons: list[StopCount]


class Turn(_View):
    """One call of an instance. Duration, TTFT and reasoning are empty when the call was not measured."""

    seq: int
    at: str
    context: int
    cache_read_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    duration_ms: int | None
    ttft_ms: int | None
    stop_reason: str


class InstanceTurns(_View):
    instance: str
    role: str
    phase: str
    peak_context: int
    cache_hit: float
    turns: list[Turn]


class BehaviourReport(_View):
    project: str
    stop_reasons: list[StopCount]
    roles: list[RoleBehaviour]
    instances: list[InstanceTurns]


def _stops(calls: Iterable[Call]) -> list[StopCount]:
    """I motivi di fine, dal più frequente; a pari numero in ordine alfabetico."""
    counted = Counter(call.stop_reason for call in calls)
    return [
        StopCount(reason=reason, calls=n, complete=reason not in INCOMPLETE)
        for reason, n in sorted(counted.items(), key=lambda item: (-item[1], item[0]))
    ]


def _cache_hit(calls: list[Call]) -> float:
    read = sum(sums.context(call) for call in calls)
    return sum(call.cache_read_tokens for call in calls) / read if read else 0.0


def _role(name: str, calls: list[Call]) -> RoleBehaviour:
    contexts = [sums.context(call) for call in calls]
    measured = sums.measured(calls)
    return RoleBehaviour(
        role=name,
        calls=len(calls),
        instances=len({call.instance for call in calls}),
        cost_usd=sums.cost(calls),
        mean_context=sum(contexts) / len(contexts),
        max_context=max(contexts),
        cache_hit=_cache_hit(calls),
        output_tokens=sum(call.output_tokens for call in calls),
        measured=len(measured),
        reasoning_tokens=sums.reasoning_tokens(calls),
        mean_duration_ms=sums.mean_duration_ms(calls),
        median_ttft_ms=sums.median_ttft_ms(calls),
        efforts=list(dict.fromkeys(call.effort for call in measured if call.effort is not None)),
        stop_reasons=_stops(calls),
    )


def _turn(call: Call) -> Turn:
    return Turn(
        seq=call.seq,
        at=call.at,
        context=sums.context(call),
        cache_read_tokens=call.cache_read_tokens,
        output_tokens=call.output_tokens,
        reasoning_tokens=call.reasoning_tokens,
        duration_ms=call.duration_ms,
        ttft_ms=call.ttft_ms,
        stop_reason=call.stop_reason,
    )


def _instance(name: str, calls: list[Call]) -> InstanceTurns:
    return InstanceTurns(
        instance=name,
        role=calls[0].role,
        phase=calls[0].phase,
        peak_context=max(sums.context(call) for call in calls),
        cache_hit=_cache_hit(calls),
        turns=[_turn(call) for call in calls],
    )


def behaviour_report(name: str, data: ProjectData) -> BehaviourReport:
    calls = sorted(data.calls, key=lambda call: call.seq)
    roles = [_role(role, group) for role, group in sums.groups(calls, lambda call: call.role).items()]
    instances = [
        _instance(item, group) for item, group in sums.groups(calls, lambda call: call.instance).items()
    ]
    return BehaviourReport(
        project=name,
        stop_reasons=_stops(calls),
        roles=sorted(roles, key=lambda role: (-role.cost_usd, role.role)),
        instances=sorted(instances, key=lambda item: (item.turns[0].at, item.instance)),
    )
