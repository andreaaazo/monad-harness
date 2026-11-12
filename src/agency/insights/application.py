"""The insights use cases: `rebuild` and `current` keep the projection in step with the registry, the
traces and the transcripts; each of the others reads one view from it.
"""

from __future__ import annotations

from agency.insights.behaviour import BehaviourReport, behaviour_report
from agency.insights.compare import CompareReport, compare_report
from agency.insights.domain import (
    Projected,
    Provenance,
    SourceStamp,
    TranscriptImage,
    project_calls,
    provenance,
)
from agency.insights.flow import FlowReport, flow_report
from agency.insights.ports import (
    LedgerReader,
    ProjectionReader,
    ProjectionStore,
    ProjectionWriter,
    TraceReader,
    TranscriptReader,
)
from agency.insights.quality import QualityReport, quality_report
from agency.insights.replay import ReplayReport, replay_report
from agency.insights.views import ProjectReport, ProjectSummary, project_report, project_summaries

# The registry revision insights can read. A test compares it with the latest migration, so a new
# migration forces a look at whether anything changes for the readers.
READS_REVISION = "0008"


class LedgerNotReadable(Exception):
    """The registry is missing, or not at the revision insights can read."""


class ProjectionOutdated(Exception):
    """The projection is missing, or has an old schema: `agency insights` rebuilds it."""


def _why(revision: str | None) -> str:
    if revision is None:
        return "registro precedente alle migrazioni: esegui agency migrate"
    if int(revision) < int(READS_REVISION):
        return (
            f"registro alla revisione {revision}, insights legge la {READS_REVISION}: esegui agency migrate"
        )
    return f"registro alla revisione {revision}, più nuova della {READS_REVISION}: aggiorna insights"


def _stamps(registry: LedgerReader, traces: TraceReader, transcripts: TranscriptReader) -> list[SourceStamp]:
    return registry.stamp() + traces.stamp() + transcripts.stamp()


def rebuild(
    registry: LedgerReader,
    traces: TraceReader,
    transcripts: TranscriptReader,
    projection: ProjectionWriter,
    built_at: str,
) -> Provenance:
    """Rebuilds the whole projection, or raises `LedgerNotReadable` for a registry at another revision."""
    # Stamped before reading: a write in the meantime shows up as a change next time.
    sources = _stamps(registry, traces, transcripts)
    revision = registry.revision()
    if revision != READS_REVISION:
        raise LedgerNotReadable(_why(revision))
    snapshot, reading, conversations = registry.read(), traces.read(), transcripts.read()
    calls = project_calls(snapshot.usage, snapshot.tickets, reading.measures)
    projected = Projected(
        calls=calls,
        projects=snapshot.projects,
        tickets=list(snapshot.tickets.values()),
        gates=snapshot.gates,
        concepts=snapshot.concepts,
        judgments=snapshot.judgments,
        events=snapshot.events,
        checks=snapshot.checks,
        tool_calls=conversations.calls,
        runs=snapshot.runs,
    )
    built = provenance(
        calls,
        built_at=built_at,
        sources=sources,
        revision=revision,
        unreadable=reading.unreadable,
        unreadable_transcripts=conversations.unreadable,
    )
    projection.replace(projected, built)
    return built


def current(
    registry: LedgerReader,
    traces: TraceReader,
    transcripts: TranscriptReader,
    projection: ProjectionStore,
    built_at: str,
) -> Provenance:
    """The up-to-date projection: rebuilt only if the registry, the traces or the transcripts changed."""
    try:
        known: Provenance | None = projection.provenance()
    except ProjectionOutdated:
        known = None
    if known is not None and known.sources == _stamps(registry, traces, transcripts):
        return known
    return rebuild(registry, traces, transcripts, projection, built_at)


def report(projection: ProjectionReader, project: str) -> ProjectReport:
    """A project's report from the projection: an unknown project has an empty report."""
    return project_report(project, projection.project(project), projection.provenance())


def flow(projection: ProjectionReader, project: str) -> FlowReport:
    """The phases view: from the ideas to the delivery, the steps back, and where the work stopped."""
    return flow_report(project, projection.project(project))


def behaviour(projection: ProjectionReader, project: str) -> BehaviourReport:
    """The model view: role by role and turn by turn."""
    return behaviour_report(project, projection.project(project))


def quality(projection: ProjectionReader, project: str) -> QualityReport:
    """The tools and QA view: checks, tool refusals and steps back, with their reasons."""
    return quality_report(project, projection.project(project))


def compare(projection: ProjectionReader, before: str, after: str) -> CompareReport:
    """The compare view: two projects side by side, their fingerprints, the blind judgments between them."""
    return compare_report(
        before,
        projection.project(before),
        after,
        projection.project(after),
        projection.judgments(),
        projection.provenance(),
    )


def replay(
    projection: ProjectionReader, transcripts: TranscriptReader, project: str, instance: str
) -> ReplayReport | None:
    """An instance's replay view, or None without a transcript: the transcript is read now, whole."""
    record = transcripts.transcript(project, instance)
    if record is None:
        return None
    return replay_report(record, [call for call in projection.calls(project) if call.instance == instance])


def image(transcripts: TranscriptReader, project: str, instance: str, index: int) -> TranscriptImage | None:
    """Image `index` of the transcript, or None if it is missing or of a type the dashboard never serves."""
    return transcripts.image(project, instance, index)


def projects(projection: ProjectionReader) -> list[ProjectSummary]:
    """The project list: every project the registry knows, with its totals."""
    return project_summaries(projection.projects(), projection.calls())
