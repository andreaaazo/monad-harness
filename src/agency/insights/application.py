"""Il caso d'uso di insights: rigenerare la proiezione da registro e tracce."""

from __future__ import annotations

from agency.insights.behaviour import BehaviourReport, behaviour_report
from agency.insights.compare import CompareReport, compare_report
from agency.insights.domain import Projected, Provenance, SourceStamp, project_calls, provenance
from agency.insights.flow import FlowReport, flow_report
from agency.insights.ports import (
    ProjectionReader,
    ProjectionStore,
    ProjectionWriter,
    RegistryReader,
    TraceReader,
    TranscriptReader,
)
from agency.insights.quality import QualityReport, quality_report
from agency.insights.views import ProjectReport, ProjectSummary, project_report, project_summaries

# La revisione del registro che insights sa leggere. Un test la confronta con l'ultima migrazione:
# una migrazione nuova obbliga a guardare se cambia qualcosa per chi legge.
READS_REVISION = "0005"


class RegistryNotReadable(Exception):
    """Il registro non c'è, oppure non è alla revisione che insights sa leggere."""


class ProjectionOutdated(Exception):
    """La proiezione non c'è, oppure ha uno schema vecchio: si rigenera con agency insights."""


def _why(revision: str | None) -> str:
    if revision is None:
        return "registro precedente alle migrazioni: esegui agency migrate"
    if int(revision) < int(READS_REVISION):
        return (
            f"registro alla revisione {revision}, insights legge la {READS_REVISION}: esegui agency migrate"
        )
    return f"registro alla revisione {revision}, più nuova della {READS_REVISION}: aggiorna insights"


def _stamps(
    registry: RegistryReader, traces: TraceReader, transcripts: TranscriptReader
) -> list[SourceStamp]:
    return registry.stamp() + traces.stamp() + transcripts.stamp()


def rebuild(
    registry: RegistryReader,
    traces: TraceReader,
    transcripts: TranscriptReader,
    projection: ProjectionWriter,
    built_at: str,
) -> Provenance:
    sources = _stamps(
        registry, traces, transcripts
    )  # prima di leggere: una scrittura nel frattempo si vedrà dopo
    revision = registry.revision()
    if revision != READS_REVISION:
        raise RegistryNotReadable(_why(revision))
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
    registry: RegistryReader,
    traces: TraceReader,
    transcripts: TranscriptReader,
    projection: ProjectionStore,
    built_at: str,
) -> Provenance:
    """La proiezione aggiornata: si rigenera solo se registro, tracce o trascrizioni sono cambiati."""
    try:
        known: Provenance | None = projection.provenance()
    except ProjectionOutdated:
        known = None
    if known is not None and known.sources == _stamps(registry, traces, transcripts):
        return known
    return rebuild(registry, traces, transcripts, projection, built_at)


def report(projection: ProjectionReader, project: str) -> ProjectReport:
    """Il rapporto di un progetto dalla proiezione: un progetto sconosciuto ha un rapporto vuoto."""
    return project_report(project, projection.project(project), projection.provenance())


def flow(projection: ProjectionReader, project: str) -> FlowReport:
    """La vista Fasi: dalle idee alla consegna, i passi indietro e dove si è fermato."""
    return flow_report(project, projection.project(project))


def behaviour(projection: ProjectionReader, project: str) -> BehaviourReport:
    """La vista Modello: ruolo per ruolo e turno per turno."""
    return behaviour_report(project, projection.project(project))


def quality(projection: ProjectionReader, project: str) -> QualityReport:
    """La vista Strumenti e QA: controlli, rifiuti degli strumenti e passi indietro, con il loro motivo."""
    return quality_report(project, projection.project(project))


def compare(projection: ProjectionReader, before: str, after: str) -> CompareReport:
    """La vista Confronto: due progetti affiancati, le loro impronte, i giudizi alla cieca fra loro."""
    return compare_report(
        before,
        projection.project(before),
        after,
        projection.project(after),
        projection.judgments(),
        projection.provenance(),
    )


def projects(projection: ProjectionReader) -> list[ProjectSummary]:
    return project_summaries(projection.projects(), projection.calls())
