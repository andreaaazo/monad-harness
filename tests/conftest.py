"""Aiuti comuni ai test."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from agency.config import REPO_ROOT
from agency.contracts.layout import DataLayout
from agency.insights import application
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.registry import ReadOnlyRegistry
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import JsonlTranscripts
from agency.insights.views import ProjectReport

# Il registro vero: nessuna prova lo scrive. I -shm cambiano anche a leggerlo, e restano fuori dal confronto.
REAL_DATA = REPO_ROOT / ".data"
_REAL_DATA_KEY = pytest.StashKey[dict[str, tuple[int, int]]]()


def _real_data() -> dict[str, tuple[int, int]]:
    if not REAL_DATA.is_dir():
        return {}
    return {
        str(path.relative_to(REAL_DATA)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in REAL_DATA.rglob("*")
        if path.is_file() and not path.name.endswith("-shm")
    }


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config.stash[_REAL_DATA_KEY] = _real_data()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Una prova che scrive nel .data vero fa fallire tutta la sessione, e dice quale file ha toccato."""
    before, after = session.config.stash[_REAL_DATA_KEY], _real_data()
    touched = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    if touched:
        print(f"\nLe prove hanno scritto nel registro vero {REAL_DATA}: {', '.join(touched)}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def report_of(tmp_path: Path) -> Callable[[Path, str], ProjectReport]:
    """Il rapporto di un progetto dal registro dato, attraverso insights: come lo fa la CLI."""

    def read(ledger: Path, project: str) -> ProjectReport:
        projection = SqliteProjection(tmp_path / "insights.sqlite")
        traces, transcripts = JsonlTraces(tmp_path / "traces.jsonl"), JsonlTranscripts(DataLayout(tmp_path))
        application.rebuild(
            ReadOnlyRegistry(ledger), traces, transcripts, projection, "2026-11-02T12:00:00+00:00"
        )
        return application.report(projection, project)

    return read
