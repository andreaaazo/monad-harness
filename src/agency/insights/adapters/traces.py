"""Le tracce dell'SDK, lette da `traces.jsonl`: durata, TTFT, effort e ragionamento di ogni richiesta.

Le tracce sono sacrificabili (ADR-0010): se mancano, la proiezione ha meno misure, non un errore. Una riga
tagliata da un processo ucciso si conta e si salta.
"""

from __future__ import annotations

import json
from pathlib import Path

from agency.insights.adapters.stamps import stamp
from agency.insights.domain import SourceStamp, TraceMeasure
from agency.insights.ports import TraceReading

SPAN = "anthropic.messages.create"
REQUEST = "anthropic.request.id"
FIRST_CHUNK = "gen_ai.response.time_to_first_chunk"  # secondi, fino al primo content_block_delta
EFFORT = "gen_ai.request.reasoning.level"
REASONING = "gen_ai.usage.reasoning.output_tokens"


def _measure(record: dict) -> TraceMeasure | None:
    attributes = record.get("attributes") or {}
    request_id = attributes.get(REQUEST)
    if record.get("name") != SPAN or not request_id:
        return None
    start, end = record.get("start"), record.get("end")
    first = attributes.get(FIRST_CHUNK)
    return TraceMeasure(
        request_id=request_id,
        duration_ms=round((end - start) / 1_000_000) if start is not None and end is not None else None,
        ttft_ms=round(first * 1000) if first is not None else None,
        effort=attributes.get(EFFORT),
        reasoning_tokens=attributes.get(REASONING),
    )


class JsonlTraces:
    def __init__(self, path: Path) -> None:
        self.path = path

    def stamp(self) -> list[SourceStamp]:
        return [stamp(self.path)]

    def read(self) -> TraceReading:
        measures: dict[str, TraceMeasure] = {}
        unreadable = 0
        if not self.path.is_file():
            return TraceReading(measures={}, unreadable=0)
        with self.path.open(encoding="utf-8") as lines:
            for line in lines:
                if not line.strip():
                    continue
                try:
                    measure = _measure(json.loads(line))
                except (ValueError, TypeError):
                    unreadable += 1
                    continue
                if measure is not None:
                    measures[measure.request_id] = measure
        return TraceReading(measures=measures, unreadable=unreadable)
