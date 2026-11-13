"""An instance's transcript: append-only, and what lets an interrupted instance resume."""

from __future__ import annotations

import json
from pathlib import Path

from agency.contracts.outcome import Outcome


class Transcript:
    """One JSON line per message, then the outcome when the instance closes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._repair()

    def _repair(self) -> None:
        """A killed process can leave half a line at the end. This is the only rewrite of the past: a complete
        last line gets its newline, a torn one is dropped (it was never sent)."""
        if not self.path.exists():
            return
        raw = self.path.read_bytes()
        if not raw or raw.endswith(b"\n"):
            return
        head, _, tail = raw.rpartition(b"\n")
        try:
            json.loads(tail)
        except ValueError:
            self.path.write_bytes(head + b"\n" if head else b"")
        else:
            self.path.write_bytes(raw + b"\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def messages(self) -> list[dict]:
        """The model history to resume from."""
        return [entry["message"] for entry in self.entries() if "message" in entry]

    def outcome(self) -> Outcome | None:
        """The outcome recorded when the instance closed, or None while it is open."""
        recorded = next((entry["outcome"] for entry in self.entries() if "outcome" in entry), None)
        return None if recorded is None else Outcome.model_validate(recorded)

    def _write(self, entry: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()

    def append(self, message: dict, request_id: str | None = None, raw: list[dict] | None = None) -> None:
        """`request_id` ties a model answer to its `usage` row: the Replay reads it, resuming reads only the
        message. `raw` is the model's content before the fallback filter, kept for audit."""
        entry = {"message": message} | ({"request_id": request_id} if request_id else {})
        self._write(entry | ({"raw": raw} if raw is not None else {}))

    def finish(self, outcome: Outcome) -> None:
        """Records the outcome: a resumed run returns it instead of redoing the work."""
        self._write({"outcome": outcome.model_dump(mode="json")})
