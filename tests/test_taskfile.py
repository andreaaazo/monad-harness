"""L'ingresso unico dei comandi è Taskfile.yml, e `make` ne è l'alias (ADR-0020, ADR-0039).

Le prove leggono il Taskfile con Task stesso, che viene da mise.toml: `--list-all --json` per i nomi,
`--dry` per i comandi, senza eseguirne nessuno.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

from agency.config import REPO_ROOT

TASKFILE = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")
# I comandi del Makefile di prima, nel loro ordine: `task check` deve fare esattamente questo.
CHECK = [
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run lint-imports",
    "uv run pyright",
    "uv run pytest",
    "pnpm --dir web run api:check",
    "pnpm --dir web run typecheck",
    "pnpm --dir web run test",
    "pnpm --dir web run defenses",
    "pnpm --dir web run build:e2e",
    "pnpm --dir web exec playwright test",
]
ALIASES = ["check", "lint", "imports", "types", "test", "web", "e2e", "schemas", "doctor", "dashboard"]


def task(*arguments: str) -> str:
    binary = shutil.which("task")
    if binary is None:
        pytest.fail("Task manca dal PATH: viene da mise.toml, si esegue con mise attivo o con `mise exec --`")
    done = subprocess.run([binary, *arguments], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return done.stdout + done.stderr


def commands(name: str, *options: str) -> list[str]:
    """I comandi che `task <name>` eseguirebbe, in ordine, come li stampa `--dry`. Con `--force` anche quelli
    di un task già aggiornato, come la build."""
    dry = task("--dry", *options, name)
    return [match[1].strip() for match in re.finditer(r"^task: \[[^\]]+\] (.+)$", dry, re.MULTILINE)]


def test_every_command_the_studio_uses_has_its_task() -> None:
    listed = {item["name"] for item in json.loads(task("--list-all", "--json"))["tasks"]}
    expected = {"setup", "dashboard:api", "dashboard:ui", "dashboard:build", "dashboard:dev", *ALIASES}
    assert expected <= listed, sorted(expected - listed)


def test_check_runs_every_control_in_order() -> None:
    assert commands("check") == CHECK


def make(name: str) -> str:
    """Cosa farebbe `make <name>`, anche quando la prova gira dentro un altro make (come `make check`)."""
    outer = {"MAKEFLAGS", "MAKELEVEL", "MFLAGS", "MAKEOVERRIDES"}
    environment = {key: value for key, value in os.environ.items() if key not in outer}
    dry = subprocess.run(
        ["make", "--no-print-directory", "-n", name],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return dry.stdout


def test_make_is_only_an_alias_of_task() -> None:
    """Con mise exec, make funziona anche senza mise attivo nella shell."""
    for name in ALIASES:
        assert make(name).strip() == f"mise exec -- task {name}", name
    assert make("setup").split() == ["mise", "install", "mise", "exec", "--", "task", "setup"]


def test_the_taskfile_never_loads_dotenv_and_keeps_next_telemetry_off() -> None:
    """La chiave sta in .env e la legge solo il gateway: un dotenv la darebbe a ogni comando."""
    assert not re.search(r"^\s*dotenv:", TASKFILE, re.MULTILINE)
    assert re.search(r'^env:\n  NEXT_TELEMETRY_DISABLED: "1"$', TASKFILE, re.MULTILINE)


def test_the_dashboard_starts_api_and_interface_together_and_stops_both_if_one_stops() -> None:
    summary = task("--summary", "dashboard")
    assert "dashboard:api" in summary and "dashboard:ui" in summary
    for name in ("dashboard", "dashboard:dev"):
        block = re.search(rf"^  {re.escape(name)}:\n((?:    .*\n|\n)+)", TASKFILE, re.MULTILINE)
        assert block is not None and "    failfast: true\n" in block[1], name
    # L'interfaccia di produzione parte dalla sua build, rifatta solo se cambiano le fonti. Task ne tiene
    # l'impronta in .task/, che non si versiona.
    ignored = subprocess.run(
        ["git", "check-ignore", ".task/checksum/x"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert ignored.stdout.strip() == ".task/checksum/x"
    assert commands("dashboard:ui", "--force")[-2:] == [
        "pnpm --dir web run build",
        "pnpm --dir web run start",
    ]
