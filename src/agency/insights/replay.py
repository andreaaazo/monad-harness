"""La vista Replay: un'istanza turno per turno, con le misure di ogni chiamata e le risposte scartate.

La trascrizione dice cosa ha scritto il modello e cosa gli hanno risposto gli strumenti; `usage` dice quanto è
costata ogni chiamata. Si legano per `request_id`, che il motore scrive accanto a ogni risposta dalle
trascrizioni di M1.6. Per quelle di prima si legano per ordine: il ciclo dell'agente non mette in
trascrizione una risposta troncata (`max_tokens`), che richiede, né un rifiuto (`refusal`), dopo cui blocca
il ticket (agents/loop.py). Tolte quelle, ogni chiamata è un turno; se i conti non tornano, nessun turno
prende le misure di un altro.

Una chiamata senza turno si mostra dove è avvenuta: prima del turno che la segue, o in fondo.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agency.insights import sums
from agency.insights.domain import Call, ImageRef, TranscriptRecord

NOT_IN_TRANSCRIPT = frozenset({"max_tokens", "refusal"})


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Alignment(StrEnum):
    """Come si sono legati turni e chiamate."""

    BY_REQUEST = "per richiesta"
    BY_ORDER = "per ordine"
    NONE = "nessuna"


class Measured(_View):
    """Una chiamata: quanto è costata, quanto contesto ha letto, quanto ha aspettato, perché si è fermata."""

    seq: int
    cost_usd: float
    context: int
    cache_read_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    duration_ms: int | None
    ttft_ms: int | None
    stop_reason: str


class ReplayTool(_View):
    name: str
    input: str
    answered: bool
    refused: bool
    result: str
    images: list[ImageRef]


class ReplayTurn(_View):
    """Un turno: la chiamata che lo ha prodotto, quelle scartate prima, ciò che il modello ha pensato,
    scritto e chiesto, e i messaggi dell'harness che lo seguono."""

    number: int
    measured: Measured | None
    discarded: list[Measured]
    thinking: list[str]
    hidden_thinking: int
    text: list[str]
    tools: list[ReplayTool]
    notes: list[str]


class ReplayReport(_View):
    project: str
    instance: str
    ticket_id: str
    role: str
    phase: str
    task: str
    alignment: Alignment
    calls: int
    cost_usd: float
    images: int
    outcome_state: str | None
    outcome_note: str
    unreadable: int
    turns: list[ReplayTurn]
    trailing_discarded: list[Measured]


def _measured(call: Call) -> Measured:
    return Measured(
        seq=call.seq,
        cost_usd=call.cost_usd,
        context=sums.context(call),
        cache_read_tokens=call.cache_read_tokens,
        output_tokens=call.output_tokens,
        reasoning_tokens=call.reasoning_tokens,
        duration_ms=call.duration_ms,
        ttft_ms=call.ttft_ms,
        stop_reason=call.stop_reason,
    )


def _match(record: TranscriptRecord, calls: list[Call]) -> tuple[Alignment, list[Call | None]]:
    """La chiamata di ogni turno, o None."""
    ids = [turn.request_id for turn in record.turns]
    if any(ids):
        by_id = {call.request_id: call for call in calls}
        return Alignment.BY_REQUEST, [by_id.get(request_id) if request_id else None for request_id in ids]
    kept = [call for call in calls if call.stop_reason not in NOT_IN_TRANSCRIPT]
    if calls and len(kept) == len(record.turns):
        return Alignment.BY_ORDER, list(kept)
    return Alignment.NONE, [None for _ in record.turns]


def replay_report(record: TranscriptRecord, calls: list[Call]) -> ReplayReport:
    calls = sorted(calls, key=lambda call: call.seq)
    alignment, matched = _match(record, calls)
    used = {call.seq for call in matched if call is not None}
    # Le chiamate senza turno, ognuna davanti al primo turno che viene dopo di lei.
    waiting = [call for call in calls if call.seq not in used] if alignment is not Alignment.NONE else []
    turns: list[ReplayTurn] = []
    for number, (turn, call) in enumerate(zip(record.turns, matched, strict=True), start=1):
        before = [item for item in waiting if call is not None and item.seq < call.seq]
        waiting = [item for item in waiting if item not in before]
        turns.append(
            ReplayTurn(
                number=number,
                measured=_measured(call) if call is not None else None,
                discarded=[_measured(item) for item in before],
                thinking=turn.thinking,
                hidden_thinking=turn.hidden_thinking,
                text=turn.text,
                tools=[
                    ReplayTool(
                        name=tool.name,
                        input=tool.input,
                        answered=tool.answered,
                        refused=tool.refused,
                        result=tool.result,
                        images=tool.images,
                    )
                    for tool in turn.tools
                ],
                notes=turn.notes,
            )
        )
    first = calls[0] if calls else None
    return ReplayReport(
        project=record.project,
        instance=record.instance,
        ticket_id=first.ticket_id if first else "",
        role=first.role if first else "",
        phase=first.phase if first else "",
        task=record.task,
        alignment=alignment,
        calls=len(calls),
        cost_usd=sums.cost(calls),
        images=record.images,
        outcome_state=record.outcome_state,
        outcome_note=record.outcome_note,
        unreadable=record.unreadable,
        turns=turns,
        trailing_discarded=[_measured(item) for item in waiting],
    )
