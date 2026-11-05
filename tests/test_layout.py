"""Where the data lives (docs/audit/PLAN.md, Task 1.15): a safety net for Tasks 2.15, 6.11 and 6.12."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agency.config import Settings
from agency.contracts.layout import DataLayout

SERVER_ROOT = "from agency.entrypoints.server import settings; print(settings.AGENCY_DATA_DIR)"


def paths(layout: DataLayout) -> tuple[Path, ...]:
    return (
        layout.ledger,
        layout.checkpoints,
        layout.artifacts,
        layout.traces,
        layout.insights,
        layout.transcripts,
        layout.transcript("p", "i"),
    )


def test_data_paths_under_a_root() -> None:
    layout = DataLayout(Path("/r"))
    assert paths(layout) == (
        Path("/r/ledger.sqlite"),
        Path("/r/checkpoints.sqlite"),
        Path("/r/artifacts"),
        Path("/r/traces.jsonl"),
        Path("/r/insights.sqlite"),
        Path("/r/runs"),
        Path("/r/runs/p/i.jsonl"),
    )
    # In Docker the projection lives elsewhere, so the container adds no file next to the registry (ADR-0040).
    assert DataLayout(Path("/r"), projection=Path("/m")).insights == Path("/m/insights.sqlite")

    settings = Settings(data_dir=Path("/r"), projects_dir=Path("/q"), _env_file=None)  # type: ignore[call-arg]
    assert paths(settings.layout) == paths(layout)
    shortcuts = (
        settings.ledger_path,
        settings.checkpoints_path,
        settings.artifacts_dir,
        settings.traces_path,
        settings.insights_path,
    )
    assert shortcuts == paths(layout)[:5]
    assert settings.project_dir("p") == Path("/q/p")


def test_engine_and_server_take_the_data_root_from_different_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.env` moves the engine's data root, not the server's: the server never reads `.env` (ADR-0031)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_")}
    for key in set(os.environ) - set(environment):
        monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    default = Settings(_env_file=None).data_dir  # type: ignore[call-arg]
    (tmp_path / ".env").write_text("AGENCY_DATA_DIR=altrove\n", encoding="utf-8")

    engine = Settings().ledger_path  # type: ignore[call-arg]
    started = subprocess.run(
        [sys.executable, "-c", SERVER_ROOT], cwd=tmp_path, env=environment, capture_output=True, text=True
    )

    # Pins current behavior of STR-001; phase 2 (Tasks 2.15-2.16) flips these assertions: one absolute root.
    assert default == Path(".data")  # relative: it follows whatever directory the command runs from
    assert engine == Path("altrove/ledger.sqlite")
    assert started.returncode == 0, started.stderr
    assert Path(started.stdout.strip()) == tmp_path.resolve() / ".data"


def test_project_names_become_folders_unchecked(tmp_path: Path) -> None:
    data, projects = tmp_path / "data", tmp_path / "projects"
    settings = Settings(data_dir=data, projects_dir=projects, _env_file=None)  # type: ignore[call-arg]

    # Pins current behavior of COR-013; phase 2 (Task 2.24) flips these assertions: each name is refused.
    assert settings.project_dir("../fuori") == tmp_path.resolve() / "fuori"  # outside projects/
    assert settings.project_dir("acme/v2") == projects.resolve() / "acme" / "v2"  # too deep for insights
    assert settings.project_dir("") == projects.resolve()  # the projects folder itself
    assert settings.layout.transcript("../fuori", "i") == data / "runs" / ".." / "fuori" / "i.jsonl"
