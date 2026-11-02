"""Il caso d'uso di insights: rigenerare la proiezione da registro e tracce."""

from __future__ import annotations

from agency.insights.domain import Provenance, project_calls, provenance
from agency.insights.ports import ProjectionWriter, RegistryReader, TraceReader

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


def rebuild(
    registry: RegistryReader, traces: TraceReader, projection: ProjectionWriter, built_at: str
) -> Provenance:
    revision = registry.revision()
    if revision != READS_REVISION:
        raise RegistryNotReadable(_why(revision))
    snapshot, reading = registry.read(), traces.read()
    calls = project_calls(snapshot.usage, snapshot.tickets, reading.measures)
    built = provenance(calls, built_at=built_at, revision=revision, unreadable=reading.unreadable)
    projection.replace(calls, built)
    return built
