"""Le tracce restano sulla macchina e non contengono testo dei materiali."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class JsonlExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self.path.open("a", encoding="utf-8") as handle:
            for span in spans:
                record = {
                    "name": span.name,
                    "start": span.start_time,
                    "end": span.end_time,
                    "trace": f"{span.context.trace_id:032x}" if span.context else "",
                    "attributes": dict(span.attributes or {}),
                }
                handle.write(json.dumps(record, default=str) + "\n")
        return SpanExportResult.SUCCESS


_configured = False


def configure(data_dir: Path) -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlExporter(data_dir / "traces.jsonl")))
    trace.set_tracer_provider(provider)
    _configured = True
