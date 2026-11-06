"""Dove stanno i dati in `.data/`: un solo proprietario, per il motore che scrive e per chi legge.

Il server del cruscotto lo usa senza passare da `agency.config`, che legge `.env` e quindi la chiave API.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataLayout:
    """`projection` è dove sta la proiezione di insights, se non accanto al registro. In Docker sta in
    memoria, e il container non aggiunge file al registro (ADR-0040)."""

    root: Path
    projection: Path | None = None

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
        return (self.projection or self.root) / "insights.sqlite"

    @property
    def transcripts(self) -> Path:
        """Le trascrizioni delle istanze, una cartella per progetto."""
        return self.root / "runs"

    def transcript(self, project: str, instance: str) -> Path:
        return self.transcripts / project / f"{instance}.jsonl"

    def ops_inputs(self, project: str, instance: str) -> Path:
        """The files the harness writes for an instance's sandbox, bound read-only at /ops (ADR-0044)."""
        return self.ops_records(project, instance) / "in"

    def ops_records(self, project: str, instance: str) -> Path:
        """The harness's record of an instance's tool runs, read on resume. No sandbox sees it (ADR-0044)."""
        return self.root / "ops" / project / instance
