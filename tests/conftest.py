"""Shared test helpers, and the guard that no test writes into the real registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from agency.config import REPO_ROOT, Settings
from agency.contracts.layout import DataLayout
from agency.insights import application
from agency.insights.adapters.ledger import ReadOnlyLedger
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import JsonlTranscripts
from agency.insights.views import ProjectReport

# The real registry: no test writes it. The -shm files change even on a read, so they stay out of
# the comparison.
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
    """A test that writes into the real .data fails the whole session, and says which file it touched."""
    before, after = session.config.stash[_REAL_DATA_KEY], _real_data()
    touched = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    if touched:
        print(f"\nTests wrote into the real registry {REAL_DATA}: {', '.join(touched)}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads a `.env`: the checkout's own holds the operator's real API key (ADR-0045).

    A test about `.env` passes its file explicitly, as `Settings(_env_file=...)`.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def report_of(tmp_path: Path) -> Callable[[Path, str], ProjectReport]:
    """A project's report from the given registry, through insights, as the CLI does it."""

    def read(ledger: Path, project: str) -> ProjectReport:
        projection = SqliteProjection(tmp_path / "insights.sqlite")
        traces, transcripts = JsonlTraces(tmp_path / "traces.jsonl"), JsonlTranscripts(DataLayout(tmp_path))
        application.rebuild(
            ReadOnlyLedger(ledger), traces, transcripts, projection, "2026-11-02T12:00:00+00:00"
        )
        return application.report(projection, project)

    return read
