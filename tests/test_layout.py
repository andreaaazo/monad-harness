"""Where the data lives (docs/audit/PLAN.md, Task 1.15): a safety net for Tasks 2.15, 6.11 and 6.12."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agency import cli
from agency.config import REPO_ROOT, DotenvHoldsSetting, Settings
from agency.contracts.layout import DataLayout
from agency.contracts.project import ProjectName, parse_project_name
from agency.runtime import open_session
from agency.tools.craft import CommandIndex
from support.scripted import ScriptedTransport

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
        layout.transcript(ProjectName("p"), "i"),
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
    assert settings.project_dir(ProjectName("p")) == Path("/q/p")


def test_the_work_folder_the_craft_index_and_the_blind_copies_have_one_owner() -> None:
    """The paths Task 6.11 moved into DataLayout and Settings, where every caller now takes them."""
    layout = DataLayout(Path("/r"))
    assert (layout.craft_index, layout.blind("c1")) == (Path("/r/craft-index"), Path("/r/blind/c1"))
    settings = Settings(data_dir=Path("/r"), projects_dir=Path("/q"), _env_file=None)  # type: ignore[call-arg]
    assert settings.work_dir(ProjectName("p")) == Path("/q/p/work")


def test_a_session_keeps_the_craft_index_cache_under_the_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commands VectorCraft lists are cached in `<data root>/craft-index`, beside the registry."""
    cache_dirs: list[Path] = []

    def load(cls: type[CommandIndex], cache_dir: Path, app: str = "vectorcraft") -> CommandIndex:
        cache_dirs.append(cache_dir)
        return cls([])

    monkeypatch.setattr(CommandIndex, "load", classmethod(load))
    settings = Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "q", _env_file=None)  # type: ignore[call-arg]
    open_session(settings, ScriptedTransport([]))
    assert cache_dirs == [tmp_path / "data" / "craft-index"]


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


def test_names_that_would_leave_projects_are_refused_at_the_boundary() -> None:
    for name in ["../fuori", "acme/v2", ""]:  # outside projects/, too deep for insights, the folder itself
        with pytest.raises(ValueError, match="nome di progetto non valido"):
            parse_project_name(name)


OLD_ENV_EXAMPLE = """# Copia in .env. Non committare mai la chiave.
ANTHROPIC_API_KEY=
# Dove vivono registro, checkpoint e artefatti locali.
AGENCY_DATA_DIR=.data
AGENCY_EXPLORER_EFFORT=high
AGENCY_PROPOSAL_EFFORT=high
AGENCY_EXPLORERS=5
AGENCY_MAX_PARALLEL=5
"""


def test_dotenv_provides_only_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`.env` is read by the engine alone, so it holds the key and nothing else (ADR-0045)."""
    for name in set(os.environ):
        if name.startswith("AGENCY_"):
            monkeypatch.delenv(name)
    dotenv = tmp_path / ".env"

    dotenv.write_text("# a comment\nOTHER=1\nAGENCY_ANTHROPIC_API_KEY=sk-test\n")
    assert Settings(_env_file=dotenv).anthropic_api_key.get_secret_value() == "sk-test"  # type: ignore[call-arg, union-attr]

    # The first offending variable in file order is named, whatever its value.
    for line in ("AGENCY_EXPLORERS=9", "AGENCY_EXPLORERS=", "AGENCY_EXPLORERS"):
        dotenv.write_text(f"ANTHROPIC_API_KEY=sk-test\n{line}\nAGENCY_DATA_DIR=/x\n")
        with pytest.raises(DotenvHoldsSetting) as refused:
            Settings(_env_file=dotenv)  # type: ignore[call-arg]
        assert refused.value.name == "AGENCY_EXPLORERS"

    # Also when the process environment sets the same variable.
    monkeypatch.setenv("AGENCY_EXPLORERS", "3")
    with pytest.raises(DotenvHoldsSetting):
        Settings(_env_file=dotenv)  # type: ignore[call-arg]

    # The process environment keeps working.
    dotenv.write_text("ANTHROPIC_API_KEY=sk-test\n")
    assert Settings(_env_file=dotenv).explorers == 3  # type: ignore[call-arg]


def test_an_old_env_example_copy_stops_with_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An old `.env.example` copy stops the engine before it starts or creates anything (Review focus 1)."""
    dotenv = tmp_path / ".env"
    dotenv.write_text(OLD_ENV_EXAMPLE)
    monkeypatch.setitem(Settings.model_config, "env_file", dotenv)
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))

    code = cli.main(["run", "acme", "brief.md", "--budget", "1"])

    out = capsys.readouterr().out
    assert code == 1
    assert out.startswith("AGENCY_DATA_DIR è in .env")
    assert len(out.splitlines()) == 1
    assert "ambiente del processo" in out
    assert not list(tmp_path.rglob("ledger.sqlite"))
