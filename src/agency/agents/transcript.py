"""Trascrizione di un'istanza: solo in aggiunta, è ciò che permette di riprendere dopo un'interruzione."""

from __future__ import annotations

import json
from pathlib import Path

from agency.contracts.outcome import Outcome


class Transcript:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._repair()

    def _repair(self) -> None:
        """Un processo ucciso può lasciare mezza riga in fondo: è l'unico punto in cui si tocca il passato."""
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
        return [entry["message"] for entry in self.entries() if "message" in entry]

    def outcome(self) -> Outcome | None:
        recorded = next((entry["outcome"] for entry in self.entries() if "outcome" in entry), None)
        return None if recorded is None else Outcome.model_validate(recorded)

    def _write(self, entry: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()

    def append(self, message: dict) -> None:
        self._write({"message": message})

    def finish(self, outcome: Outcome) -> None:
        self._write({"outcome": outcome.model_dump(mode="json")})
