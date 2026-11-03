"""I confini esterni di insights. Il caso d'uso dipende da queste porte, non da SQLite né dai file."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from agency.insights.domain import (
    Call,
    CheckRecord,
    ConceptRecord,
    EventRecord,
    GateRecord,
    JudgmentRecord,
    Projected,
    ProjectRecord,
    Provenance,
    RunRecord,
    SourceStamp,
    TicketRecord,
    ToolCallRecord,
    TraceMeasure,
    TranscriptImage,
    TranscriptRecord,
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
    events: list[EventRecord]
    checks: list[CheckRecord]
    runs: list[RunRecord]


class ProjectData(BaseModel):
    """Ciò che la proiezione sa di un progetto: le viste nascono da qui."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: ProjectRecord | None
    calls: list[Call]
    tickets: list[TicketRecord]
    gates: list[GateRecord]
    concepts: list[ConceptRecord]
    judgments: list[JudgmentRecord]
    events: list[EventRecord]
    checks: list[CheckRecord]
    tool_calls: list[ToolCallRecord]
    runs: list[RunRecord]


class TraceReading(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    measures: dict[str, TraceMeasure]
    unreadable: int


class TranscriptReading(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    calls: list[ToolCallRecord]
    unreadable: int


class RegistryReader(Protocol):
    def stamp(self) -> list[SourceStamp]:
        """I file del registro come sono ora: se cambiano, la proiezione è vecchia."""
        ...

    def revision(self) -> str | None:
        """La revisione del registro, o None se è precedente alle migrazioni."""
        ...

    def read(self) -> RegistrySnapshot: ...


class TraceReader(Protocol):
    def stamp(self) -> list[SourceStamp]: ...

    def read(self) -> TraceReading: ...


class TranscriptReader(Protocol):
    def stamp(self) -> list[SourceStamp]:
        """Una impronta per trascrizione: una che cambia, nasce o sparisce rende vecchia la proiezione."""
        ...

    def read(self) -> TranscriptReading: ...

    def transcript(self, project: str, instance: str) -> TranscriptRecord | None:
        """Un'istanza turno per turno, o None se non c'è o il nome non è quello di un'istanza."""
        ...

    def image(self, project: str, instance: str, index: int) -> TranscriptImage | None:
        """L'immagine `index` della trascrizione, solo se è di un tipo che il cruscotto serve."""
        ...


class ProjectionWriter(Protocol):
    def replace(self, projected: Projected, provenance: Provenance) -> None:
        """Sostituisce la proiezione intera, in un colpo solo: chi legge non vede mai metà lavoro."""
        ...


class ProjectionReader(Protocol):
    def project(self, name: str) -> ProjectData: ...

    def calls(self, project: str | None = None) -> list[Call]: ...

    def projects(self) -> list[ProjectRecord]: ...

    def judgments(self) -> list[JudgmentRecord]:
        """Tutti i voti: un confronto alla cieca può mettere insieme file di più progetti."""
        ...

    def provenance(self) -> Provenance: ...


class ProjectionStore(ProjectionReader, ProjectionWriter, Protocol):
    """La proiezione che si legge e si rigenera: quella che usano il rapporto e il cruscotto."""
