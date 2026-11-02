"""Aiuti comuni ai test."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from agency.insights import application
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.registry import ReadOnlyRegistry
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.views import ProjectReport


@pytest.fixture
def report_of(tmp_path: Path) -> Callable[[Path, str], ProjectReport]:
    """Il rapporto di un progetto dal registro dato, attraverso insights: come lo fa la CLI."""

    def read(ledger: Path, project: str) -> ProjectReport:
        projection = SqliteProjection(tmp_path / "insights.sqlite")
        traces = JsonlTraces(tmp_path / "traces.jsonl")
        application.rebuild(ReadOnlyRegistry(ledger), traces, projection, "2026-11-02T12:00:00+00:00")
        return application.report(projection, project)

    return read
