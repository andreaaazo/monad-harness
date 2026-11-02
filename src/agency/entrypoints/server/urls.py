"""Le URL del server: solo l'API, sotto /api/."""

from __future__ import annotations

from django.urls import path

from agency.entrypoints.server.api import api

urlpatterns = [path("api/", api.urls)]
