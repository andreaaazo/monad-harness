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
from agency.insights.domain import Provenance
from agency.insights.views import ProjectReport, ProjectSummary

# Niente pagina di documentazione: caricherebbe script da una CDN. Lo schema resta in /api/openapi.json.
api = NinjaAPI(title="Design agency: cruscotto", version="1", docs_url=None)
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


@api.get("/provenance", response=Provenance)
def provenance(request: HttpRequest) -> Provenance:
    return _projection().provenance()


@api.get("/projects", response=list[ProjectSummary])
def projects(request: HttpRequest) -> list[ProjectSummary]:
    return application.projects(_projection())


@api.get("/projects/{name}/report", response={200: ProjectReport, 404: Problem})
def report(request: HttpRequest, name: str) -> Status:
    projection = _projection()
    if name not in {summary.name for summary in application.projects(projection)}:
        return Status(404, Problem(detail=f"progetto sconosciuto: {name}"))
    return Status(200, application.report(projection, name))
