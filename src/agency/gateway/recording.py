"""Recording of a live run: every answered call, keyed by its request, for replay in tests (ADR-0048).

Replay lives in `tests/support/replay.py`: no production path answers from a recording.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from agency.gateway.transport import Transport

# The request fields the key covers: what the model is asked, not how the answer is paid for or cached.
KEYED = ("model", "system", "tools", "messages", "output_config")


def request_key(params: dict) -> str:
    """The sha256 of the canonical request: the `KEYED` fields as JSON with sorted keys and no spaces."""
    canonical = json.dumps(
        {name: params[name] for name in KEYED if name in params},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecordingTransport:
    """Wraps the live transport and appends one JSON line for each call it answered.

    The gateway sends `count_tokens` and `stream` the same params, so each line names its `kind` next to
    the key. The calls run in parallel, outside the lock; only the append holds it, so lines never
    interleave. A call that raises leaves no line.
    """

    def __init__(self, inner: Transport, path: Path) -> None:
        self.inner = inner
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def count_tokens(self, params: dict) -> int:
        tokens = self.inner.count_tokens(params)
        self._append("count_tokens", params, tokens)
        return tokens

    def stream(self, params: dict) -> dict:
        response = self.inner.stream(params)
        self._append("stream", params, response)
        return response

    def _append(self, kind: str, params: dict, response: int | dict) -> None:
        record = {"kind": kind, "key": request_key(params), "request": params, "response": response}
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
