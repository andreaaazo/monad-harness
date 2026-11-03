"""Le route del cruscotto: solo GET, ognuna chiama un caso d'uso di insights e restituisce i suoi modelli."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI, Schema, Status

from agency.contracts.layout import DataLayout
from agency.insights import application
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.registry import ReadOnlyRegistry
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import IMAGE_TYPES, JsonlTranscripts
from agency.insights.behaviour import BehaviourReport
from agency.insights.compare import CompareReport
from agency.insights.domain import Provenance
from agency.insights.flow import FlowReport
from agency.insights.quality import QualityReport
from agency.insights.replay import ReplayReport
from agency.insights.views import ProjectReport, ProjectSummary

# Niente pagina di documentazione: caricherebbe script da una CDN. Lo schema resta in /api/openapi.json.
api = NinjaAPI(
    title="Design agency: cruscotto",
    version="1",
    description="Il cruscotto in sola lettura: registro e tracce attraverso insights (ADR-0019).",
    docs_url=None,
)
_refresh = threading.Lock()  # una rigenerazione per volta: chi arriva dopo trova la proiezione già fatta


class Problem(Schema):
    detail: str


def _layout() -> DataLayout:
    return DataLayout(settings.AGENCY_DATA_DIR, settings.AGENCY_PROJECTION_DIR)


def _transcripts() -> JsonlTranscripts:
    return JsonlTranscripts(_layout())


def _projection() -> SqliteProjection:
    """La proiezione aggiornata: si rifà solo se registro, tracce o trascrizioni sono cambiati."""
    layout = _layout()
    projection = SqliteProjection(layout.insights)
    registry, traces = ReadOnlyRegistry(layout.ledger), JsonlTraces(layout.traces)
    transcripts = JsonlTranscripts(layout)
    with _refresh:
        built_at = datetime.now(UTC).isoformat(timespec="seconds")
        application.current(registry, traces, transcripts, projection, built_at)
    return projection


@api.exception_handler(application.RegistryNotReadable)
def registry_not_readable(request: HttpRequest, exc: application.RegistryNotReadable) -> HttpResponse:
    return api.create_response(request, Problem(detail=str(exc)), status=503)


# Ogni route dichiara anche il 503: l'interfaccia sa che forma ha la risposta quando il registro non si legge.
# I nomi delle operazioni sono espliciti, così i tipi TypeScript non dipendono da dove sta il codice Python.
@api.get("/provenance", response={200: Provenance, 503: Problem}, operation_id="provenance")
def provenance(request: HttpRequest) -> Provenance:
    return _projection().provenance()


@api.get("/projects", response={200: list[ProjectSummary], 503: Problem}, operation_id="listProjects")
def projects(request: HttpRequest) -> list[ProjectSummary]:
    return application.projects(_projection())


def _unknown(projection: SqliteProjection, name: str) -> Status | None:
    """Un progetto che il registro non conosce è un 404, non una vista vuota."""
    if name in {summary.name for summary in application.projects(projection)}:
        return None
    return Status(404, Problem(detail=f"progetto sconosciuto: {name}"))


@api.get(
    "/projects/{name}/report",
    response={200: ProjectReport, 404: Problem, 503: Problem},
    operation_id="projectReport",
)
def report(request: HttpRequest, name: str) -> Status:
    projection = _projection()
    unknown = _unknown(projection, name)
    return unknown if unknown is not None else Status(200, application.report(projection, name))


@api.get(
    "/projects/{name}/flow",
    response={200: FlowReport, 404: Problem, 503: Problem},
    operation_id="projectFlow",
)
def flow(request: HttpRequest, name: str) -> Status:
    projection = _projection()
    unknown = _unknown(projection, name)
    return unknown if unknown is not None else Status(200, application.flow(projection, name))


@api.get(
    "/projects/{name}/behaviour",
    response={200: BehaviourReport, 404: Problem, 503: Problem},
    operation_id="projectBehaviour",
)
def behaviour(request: HttpRequest, name: str) -> Status:
    projection = _projection()
    unknown = _unknown(projection, name)
    return unknown if unknown is not None else Status(200, application.behaviour(projection, name))


@api.get(
    "/projects/{name}/quality",
    response={200: QualityReport, 404: Problem, 503: Problem},
    operation_id="projectQuality",
)
def quality(request: HttpRequest, name: str) -> Status:
    projection = _projection()
    unknown = _unknown(projection, name)
    return unknown if unknown is not None else Status(200, application.quality(projection, name))


@api.get(
    "/compare",
    response={200: CompareReport, 400: Problem, 404: Problem, 503: Problem},
    operation_id="compareProjects",
)
def compare(request: HttpRequest, before: str, after: str) -> Status:
    """Due progetti diversi, tutti e due conosciuti dal registro."""
    if before == after:
        return Status(400, Problem(detail=f"scegli due progetti diversi: {before} due volte"))
    projection = _projection()
    for name in (before, after):
        unknown = _unknown(projection, name)
        if unknown is not None:
            return unknown
    return Status(200, application.compare(projection, before, after))


@api.get(
    "/projects/{name}/instances/{instance}/replay",
    response={200: ReplayReport, 404: Problem, 503: Problem},
    operation_id="instanceReplay",
)
def replay(request: HttpRequest, name: str, instance: str) -> Status:
    projection = _projection()
    unknown = _unknown(projection, name)
    if unknown is not None:
        return unknown
    report = application.replay(projection, _transcripts(), name, instance)
    if report is None:
        return Status(404, Problem(detail=f"nessuna trascrizione per {instance} in {name}"))
    return Status(200, report)


# Un'immagine è byte, non JSON: lo schema dice i tipi che può avere.
_PICTURE = {
    200: {
        "description": "L'immagine restituita all'istanza, nel suo tipo",
        "content": {
            media: {"schema": {"type": "string", "format": "binary"}} for media in sorted(IMAGE_TYPES)
        },
    }
}


@api.get(
    "/projects/{name}/instances/{instance}/images/{index}",
    response={404: Problem, 503: Problem},
    operation_id="instanceImage",
    openapi_extra={"responses": _PICTURE},
)
def image(request: HttpRequest, name: str, instance: str, index: int) -> HttpResponse | Status:
    """L'immagine `index` della trascrizione: solo PNG, JPEG, GIF e WebP, mai incorniciata né eseguita."""
    unknown = _unknown(_projection(), name)
    if unknown is not None:
        return unknown
    picture = application.image(_transcripts(), name, instance, index)
    if picture is None:
        return Status(404, Problem(detail=f"nessuna immagine {index} per {instance} in {name}"))
    response = HttpResponse(picture.data, content_type=picture.media_type)
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["Content-Disposition"] = "inline"
    return response
