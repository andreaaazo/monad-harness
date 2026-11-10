"""The outer boundaries of insights. The use cases depend on these ports, not on SQLite or on files."""

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
    """What insights reads from the registry, in one transaction: a consistent snapshot."""

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
    """What the projection knows about a project: the views are built from it."""

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
    """`measures` by request id; `unreadable` counts the lines that could not be read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    measures: dict[str, TraceMeasure]
    unreadable: int


class TranscriptReading(BaseModel):
    """Every tool call in the transcripts; `unreadable` counts the lines that could not be read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calls: list[ToolCallRecord]
    unreadable: int


class RegistryReader(Protocol):
    def stamp(self) -> list[SourceStamp]:
        """The registry's files as they are now: if they change, the projection is stale."""
        ...

    def revision(self) -> str | None:
        """The registry's revision, or None if it predates the migrations."""
        ...

    def read(self) -> RegistrySnapshot: ...


class TraceReader(Protocol):
    def stamp(self) -> list[SourceStamp]: ...

    def read(self) -> TraceReading: ...


class TranscriptReader(Protocol):
    def stamp(self) -> list[SourceStamp]:
        """One stamp per transcript: one that changes, appears or disappears makes the projection stale."""
        ...

    def read(self) -> TranscriptReading: ...

    def transcript(self, project: str, instance: str) -> TranscriptRecord | None:
        """An instance turn by turn, or None if it is missing or the name is not an instance's."""
        ...

    def image(self, project: str, instance: str, index: int) -> TranscriptImage | None:
        """Image `index` of the transcript, only if it is of a type the dashboard serves."""
        ...


class ProjectionWriter(Protocol):
    def replace(self, projected: Projected, provenance: Provenance) -> None:
        """Replaces the whole projection at once: a reader never sees half the work."""
        ...


class ProjectionReader(Protocol):
    def project(self, name: str) -> ProjectData: ...

    def calls(self, project: str | None = None) -> list[Call]: ...

    def projects(self) -> list[ProjectRecord]: ...

    def judgments(self) -> list[JudgmentRecord]:
        """All the votes: a blind comparison can bring together files from several projects."""
        ...

    def provenance(self) -> Provenance:
        """What the projection was built from; `ProjectionOutdated` if it is missing or of an old schema."""
        ...


class ProjectionStore(ProjectionReader, ProjectionWriter, Protocol):
    """The projection that is read and rebuilt: the one the report and the dashboard use."""
