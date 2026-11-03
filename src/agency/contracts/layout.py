"""Dove stanno i dati in `.data/`: un solo proprietario, per il motore che scrive e per chi legge.

Il server del cruscotto lo usa senza passare da `agency.config`, che legge `.env` e quindi la chiave API.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataLayout:
    root: Path

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.sqlite"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints.sqlite"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def traces(self) -> Path:
        return self.root / "traces.jsonl"

    @property
    def insights(self) -> Path:
        return self.root / "insights.sqlite"

    @property
    def transcripts(self) -> Path:
        """Le trascrizioni delle istanze, una cartella per progetto."""
        return self.root / "runs"

    def transcript(self, project: str, instance: str) -> Path:
        return self.transcripts / project / f"{instance}.jsonl"
