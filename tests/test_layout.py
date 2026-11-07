"""Where the data lives (docs/audit/PLAN.md, Task 1.15): a safety net for Tasks 2.15, 6.11 and 6.12."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agency.config import REPO_ROOT, Settings
from agency.contracts.layout import DataLayout

SERVER_ROOT = "from agency.entrypoints.server import settings; print(settings.AGENCY_DATA_DIR)"
# A fresh process, so the class keeps its own `.env` setting; `_env_file=None`, so it reads no `.env`.
ENGINE_ROOTS = (
    "from agency.config import REPO_ROOT, Settings\n"
    "settings = Settings(_env_file=None)\n"
    "dotenv = Settings.model_config['env_file']\n"
    "print(REPO_ROOT, dotenv, settings.data_dir, settings.projects_dir, sep='\\n')\n"
)


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


def test_the_default_data_root_is_the_checkout_from_any_directory(tmp_path: Path) -> None:
    """From `web/`, the engine uses the checkout's registry and `.env`, not ones in `web/` (DX-003)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_")}
    seen = []
    for folder in (tmp_path, tmp_path / "web"):
        folder.mkdir(exist_ok=True)
        done = subprocess.run(
            [sys.executable, "-c", ENGINE_ROOTS],
            cwd=folder,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        seen.append(done.stdout.splitlines())

    expected = [str(REPO_ROOT / name) for name in ("", ".env", ".data", "projects")]
    assert seen == [expected, expected]
    assert (REPO_ROOT / "registry" / "roles.json").is_file()  # the checkout the code runs from


def test_engine_and_server_resolve_the_same_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From a folder outside the checkout, with or without `AGENCY_DATA_DIR`: one root for both (ADR-0045)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_")}
    for key in set(os.environ) - set(environment):
        monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    chosen = tmp_path / "registro"

    def server_root(extra: dict[str, str]) -> Path:
        started = subprocess.run(
            [sys.executable, "-c", SERVER_ROOT],
            cwd=tmp_path,
            env=environment | extra,
            capture_output=True,
            text=True,
        )
        assert started.returncode == 0, started.stderr
        return Path(started.stdout.strip())

    default = (Settings().data_dir, server_root({}))
    monkeypatch.setenv("AGENCY_DATA_DIR", str(chosen))
    given = (Settings().data_dir, server_root({"AGENCY_DATA_DIR": str(chosen)}))

    assert default == (REPO_ROOT / ".data", REPO_ROOT / ".data")
    assert given == (chosen, chosen)


def test_project_names_become_folders_unchecked(tmp_path: Path) -> None:
    data, projects = tmp_path / "data", tmp_path / "projects"
    settings = Settings(data_dir=data, projects_dir=projects, _env_file=None)  # type: ignore[call-arg]

    # Pins current behavior of COR-013; phase 2 (Task 2.24) flips these assertions: each name is refused.
    assert settings.project_dir("../fuori") == tmp_path.resolve() / "fuori"  # outside projects/
    assert settings.project_dir("acme/v2") == projects.resolve() / "acme" / "v2"  # too deep for insights
    assert settings.project_dir("") == projects.resolve()  # the projects folder itself
    assert settings.layout.transcript("../fuori", "i") == data / "runs" / ".." / "fuori" / "i.jsonl"
