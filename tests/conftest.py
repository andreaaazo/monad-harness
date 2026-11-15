"""Shared test helpers, and the guard that no test writes into the real registry."""

from __future__ import annotations

import os
import shutil
import tempfile
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
from agency.workshop.sandbox import Sandbox, SandboxUnavailable
from support.environment import operator_variables

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


def _sandbox_problem() -> str | None:
    """None if the engine's own sandbox runs a trivial command; otherwise what went wrong, on one line."""
    if shutil.which("bwrap") is None:
        return "bwrap is not on PATH"
    with tempfile.TemporaryDirectory() as work:
        try:
            done = Sandbox(Path(work)).run(["/usr/bin/true"], timeout=30)
        except SandboxUnavailable as error:
            return str(error)
    if done.code != 0:
        first = next((line for line in done.output.splitlines() if line.strip()), "no output")
        return f"bwrap exited {done.code}: {first}"
    return None


def pytest_collection_finish(session: pytest.Session) -> None:
    """A selected `sandbox` test needs a working sandbox: without one, the session stops at once in one line.

    Those tests prove no network, no key and one writable folder, so a run that skipped them would be a false
    green. `pytest -m "not sandbox"` is the explicit way to run without them (Q10).
    """
    if not any(item.get_closest_marker("sandbox") for item in session.items):
        return
    why = _sandbox_problem()
    if why is not None:
        pytest.exit(
            f"the sandbox tests need a working bwrap sandbox, and it fails here: {why}. "
            "Check it with `task doctor`, or run without them: pytest -m 'not sandbox'",
            returncode=pytest.ExitCode.TESTS_FAILED,
        )


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


@pytest.fixture(autouse=True)
def _no_operator_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test inherits the engine's settings or the API key from the shell that runs pytest.

    An `AGENCY_EXPLORERS=2` there changed the flows the tests pin, and an `AGENCY_DATA_DIR` would point a test
    that builds default settings at the operator's registry. A test that needs one sets it itself.
    """
    for name in operator_variables(os.environ):
        monkeypatch.delenv(name)


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


# The work folders the safe-files tests take by name: one with links of each shape, one with a FIFO.


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """A work folder with a real folder and a real file, each beside a symlink of that shape to the host."""
    root, host = tmp_path / "work", tmp_path / "host"
    (root / "real").mkdir(parents=True)
    host.mkdir()
    (root / "real" / "kept.txt").write_bytes(b"dentro")
    (root / "real.txt").write_bytes(b"dentro")
    (host / "kept.txt").write_bytes(b"fuori")
    (root / "link").symlink_to(host, target_is_directory=True)
    (root / "link.txt").symlink_to(host / "kept.txt")
    return root, host


@pytest.fixture
def fifo_tree(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "work"
    (work / "real").mkdir(parents=True)
    fifo = work / "real" / "trappola.png"
    os.mkfifo(fifo)
    return work, fifo
