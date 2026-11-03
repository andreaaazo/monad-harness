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
from agency.insights.behaviour import BehaviourReport
from agency.insights.domain import Provenance
from agency.insights.flow import FlowReport
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


def _projection() -> SqliteProjection:
    """La proiezione aggiornata: si rifà solo se registro o tracce sono cambiati dall'ultima volta."""
    layout = DataLayout(settings.AGENCY_DATA_DIR)
    projection = SqliteProjection(layout.insights)
    registry, traces = ReadOnlyRegistry(layout.ledger), JsonlTraces(layout.traces)
    with _refresh:
        application.current(registry, traces, projection, datetime.now(UTC).isoformat(timespec="seconds"))
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
