"""The server's URLs: only the API, under /api/."""

from __future__ import annotations

from django.urls import path

from agency.entrypoints.server.api import api

urlpatterns = [path("api/", api.urls)]
