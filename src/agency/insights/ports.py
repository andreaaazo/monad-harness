"""I confini esterni di insights. Il caso d'uso dipende da queste porte, non da SQLite né dai file."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from agency.insights.domain import (
    Call,
    ConceptRecord,
    GateRecord,
    JudgmentRecord,
    Projected,
    ProjectRecord,
    Provenance,
    TicketRecord,
    TraceMeasure,
    UsageRecord,
)


class RegistrySnapshot(BaseModel):
    """Ciò che insights legge del registro, nella stessa transazione: una fotografia coerente."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    usage: list[UsageRecord]
    tickets: dict[str, TicketRecord]
    projects: list[ProjectRecord]
    gates: list[GateRecord]
    concepts: list[ConceptRecord]
    judgments: list[JudgmentRecord]


class ProjectData(BaseModel):
    """Ciò che la proiezione sa di un progetto: le viste nascono da qui."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: ProjectRecord | None
    calls: list[Call]
    tickets: list[TicketRecord]
    gates: list[GateRecord]
    concepts: list[ConceptRecord]
    judgments: list[JudgmentRecord]


class TraceReading(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    measures: dict[str, TraceMeasure]
    unreadable: int


class RegistryReader(Protocol):
    def revision(self) -> str | None:
        """La revisione del registro, o None se è precedente alle migrazioni."""
        ...

    def read(self) -> RegistrySnapshot: ...


class TraceReader(Protocol):
    def read(self) -> TraceReading: ...


class ProjectionWriter(Protocol):
    def replace(self, projected: Projected, provenance: Provenance) -> None:
        """Sostituisce la proiezione intera, in un colpo solo: chi legge non vede mai metà lavoro."""
        ...


class ProjectionReader(Protocol):
    def project(self, name: str) -> ProjectData: ...

    def provenance(self) -> Provenance: ...
