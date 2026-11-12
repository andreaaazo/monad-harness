"""The single entry point for commands is Taskfile.yml, and `make` is its alias (ADR-0020, ADR-0039).

The tests read the Taskfile with Task itself, which comes from mise.toml: `--list-all --json` for the names,
`--dry` for the commands, without running any of them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from agency.config import REPO_ROOT

TASKFILE = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")
# The commands of `task check`, in their order: first the fast ones, those of the pre-commit hook (ADR-0051).
FAST = [
    "uv lock --check",
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run lint-imports",
    "uv run pyright",
    "pnpm --dir web run api:check",
    "pnpm --dir web run typecheck",
    "pnpm --dir web run defenses",
]
CHECK = [
    *FAST,
    "uv run pytest",
    "pnpm --dir web run test",
    "pnpm --dir web run build:e2e",
    "pnpm --dir web exec playwright test",
]
HOOK = REPO_ROOT / ".githooks" / "pre-commit"
ALIASES = [
    "check",
    "lint",
    "format",
    "imports",
    "types",
    "test",
    "web",
    "e2e",
    "schemas",
    "doctor",
    "dashboard",
]


def task(*arguments: str) -> str:
    binary = shutil.which("task")
    if binary is None:
        pytest.fail(
            "Task is not on PATH: it comes from mise.toml, so run with mise active or through `mise exec --`"
        )
    done = subprocess.run([binary, *arguments], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return done.stdout + done.stderr


def commands(name: str, *options: str) -> list[str]:
    """The commands `task <name>` would run, in order, as `--dry` prints them. With `--force`, also those of a
    task already up to date, such as the build."""
    dry = task("--dry", *options, name)
    return [match[1].strip() for match in re.finditer(r"^task: \[[^\]]+\] (.+)$", dry, re.MULTILINE)]


def test_every_command_the_studio_uses_has_its_task() -> None:
    listed = {item["name"] for item in json.loads(task("--list-all", "--json"))["tasks"]}
    expected = {
        "setup",
        "dashboard:api",
        "dashboard:ui",
        "dashboard:build",
        "dashboard:dev",
        "docker:up",
        "docker:down",
        *ALIASES,
    }
    assert expected <= listed, sorted(expected - listed)


def test_check_runs_every_control_in_order() -> None:
    assert commands("check") == CHECK


def test_the_fast_checks_are_the_start_of_the_gate() -> None:
    """The hook runs `check:fast`, so a commit it lets through has passed the first part of `task check`."""
    assert commands("check:fast") == FAST
    assert commands("web") == [*FAST[-3:], "pnpm --dir web run test"]


@pytest.mark.parametrize(("status", "expected"), [(0, 0), (1, 1)])
def test_the_pre_commit_hook_runs_the_fast_checks_through_mise(
    tmp_path: Path, status: int, expected: int
) -> None:
    """A stub `mise` first on PATH stands in for the checks: the hook passes their exit status on and says
    what to do when they fail."""
    stub = tmp_path / "mise"
    seen = tmp_path / "seen.txt"
    stub.write_text(f'#!/bin/sh\necho "$@" > "{seen}"\nexit {status}\n', encoding="utf-8")
    stub.chmod(0o755)
    done = subprocess.run(
        [HOOK], cwd=REPO_ROOT, env={"PATH": f"{tmp_path}:/usr/bin:/bin"}, capture_output=True, text=True
    )
    assert done.returncode == expected
    assert seen.read_text(encoding="utf-8").split() == ["exec", "--", "task", "check:fast"]
    assert ("the fast checks failed" in done.stderr) == bool(status)


def test_the_pre_commit_hook_says_what_to_do_without_mise(tmp_path: Path) -> None:
    done = subprocess.run([HOOK], cwd=REPO_ROOT, env={"PATH": str(tmp_path)}, capture_output=True, text=True)
    assert done.returncode == 1
    assert "mise is not on PATH" in done.stderr and "--no-verify" in done.stderr


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(), reason="serve un clone git"
)
def test_check_clean_runs_setup_and_check_on_a_copy_of_the_index(tmp_path: Path) -> None:
    """`check:clean` copies what git holds, runs `setup` and `check` there and removes the copy (DX-009).

    A stub stands in for the inner `task` (Task lets TASK_EXE be set like any variable): it records where it
    ran and what it saw, so the real gate does not run twice.
    """
    stub = tmp_path / "task"
    seen = tmp_path / "seen.txt"
    stub.write_text(
        f'#!/bin/sh\n{{ echo "$1 $PWD"; ls -A; }} >> "{seen}"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    task("check:clean", f"TASK_EXE={stub}")
    lines = seen.read_text(encoding="utf-8").splitlines()
    runs = [line.split(" ", 1) for line in lines if line.startswith(("setup ", "check "))]
    assert [name for name, _ in runs] == ["setup", "check"]
    copy = Path(runs[0][1])
    assert copy != REPO_ROOT and runs[1][1] == str(copy)
    assert not copy.exists()
    listed = set(lines)
    assert {"Taskfile.yml", "pyproject.toml", "uv.lock", "web"} <= listed
    assert not {".git", ".venv", ".task"} & listed  # on the disk of the checkout, never in its index


def test_format_fixes_what_ruff_can_and_then_formats() -> None:
    """`lint` only reports; `format` writes the fixes, then the formatting that `lint` checks."""
    assert commands("format") == ["uv run ruff check --fix .", "uv run ruff format ."]


def make(*names: str) -> str:
    """What `make <names>` would do, even when the test runs inside another make (such as `make check`)."""
    outer = {"MAKEFLAGS", "MAKELEVEL", "MFLAGS", "MAKEOVERRIDES"}
    environment = {key: value for key, value in os.environ.items() if key not in outer}
    dry = subprocess.run(
        ["make", "--no-print-directory", "-n", *names],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return dry.stdout


def test_make_is_only_an_alias_of_task() -> None:
    """Through mise exec, make works even without mise active in the shell."""
    for name in ALIASES:
        assert make(name).strip() == f"mise exec -- task {name}", name
    assert make("setup").split() == ["mise", "install", "mise", "exec", "--", "task", "setup"]


def test_a_bare_make_lists_the_commands_instead_of_installing() -> None:
    assert make().strip() == "mise exec -- task"
    assert make("help").strip() == "mise exec -- task"


def test_a_stale_lock_fails_instead_of_being_rewritten() -> None:
    """`setup` installs the lock as it is, and every task runs uv with UV_LOCKED, so a pyproject.toml that the
    lock no longer matches stops the command with uv's own line instead of rewriting uv.lock (DX-004)."""
    assert commands("setup")[0] == "uv sync --locked"
    assert re.search(r'^env:\n(?:  .*\n)*  UV_LOCKED: "1"$', TASKFILE, re.MULTILINE)


def test_the_taskfile_never_loads_dotenv_and_keeps_next_telemetry_off() -> None:
    """The key is in .env and only the gateway reads it: a dotenv would hand it to every command."""
    assert not re.search(r"^\s*dotenv:", TASKFILE, re.MULTILINE)
    assert re.search(r'^env:\n  NEXT_TELEMETRY_DISABLED: "1"$', TASKFILE, re.MULTILINE)


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(), reason="serve un clone git"
)
def test_the_build_fingerprints_of_task_are_not_versioned() -> None:
    """The production interface starts from its build, redone only when the sources change. Task keeps its
    fingerprint in .task/, which is not versioned. Outside a git checkout there is no .gitignore to ask."""
    ignored = subprocess.run(
        ["git", "check-ignore", ".task/checksum/x"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert ignored.returncode == 0, f"git check-ignore exited {ignored.returncode}: {ignored.stderr.strip()}"
    assert ignored.stdout.strip() == ".task/checksum/x"


def test_the_dashboard_starts_api_and_interface_together_and_stops_both_if_one_stops() -> None:
    summary = task("--summary", "dashboard")
    assert "dashboard:api" in summary and "dashboard:ui" in summary
    for name in ("dashboard", "dashboard:dev"):
        block = re.search(rf"^  {re.escape(name)}:\n((?:    .*\n|\n)+)", TASKFILE, re.MULTILINE)
        assert block is not None and "    failfast: true\n" in block[1], name
    assert commands("dashboard:ui", "--force")[-2:] == [
        "pnpm --dir web run build",
        "pnpm --dir web run start",
    ]


def test_docker_up_gives_compose_the_host_data_root_as_agency_data_dir(tmp_path: Path) -> None:
    """`task docker:up` hands Compose AGENCY_DATA_DIR: `<root>/.data`, or the operator's value if given.

    A stub `docker` first on PATH records its AGENCY_* variables and exits 0, so no real docker runs.
    """
    stub = tmp_path / "bin" / "docker"
    stub.parent.mkdir()
    seen = tmp_path / "seen.txt"
    stub.write_text(f'#!/bin/sh\nenv | grep "^AGENCY_" > "{seen}"\n', encoding="utf-8")  # no secret on disk
    stub.chmod(0o755)
    binary = shutil.which("task")
    if binary is None:
        pytest.fail("Task is not on PATH: it comes from mise.toml, run it with mise active or `mise exec --`")

    # A copy of the Taskfile, so that `<root>/.data` is a folder of the test's own, never the checkout's.
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (root / ".data").mkdir()

    def host_side(**variables: str) -> dict[str, str]:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_DATA")}
        environment |= {"PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}"} | variables
        subprocess.run([binary, "docker:up"], cwd=root, env=environment, capture_output=True, check=True)
        lines = seen.read_text(encoding="utf-8").splitlines()
        seen.unlink()
        return dict(line.split("=", 1) for line in lines if "=" in line)

    default = host_side()
    assert default["AGENCY_DATA_DIR"] == str(root / ".data")
    assert "AGENCY_DATA" not in default
    assert host_side(AGENCY_DATA_DIR=str(tmp_path))["AGENCY_DATA_DIR"] == str(tmp_path)


@pytest.mark.parametrize(
    ("variables", "message"),
    [
        ({"AGENCY_DATA": "/vecchio/registro"}, "AGENCY_DATA non si usa più"),
        ({"AGENCY_DATA": ""}, "AGENCY_DATA non si usa più"),
        ({"AGENCY_DATA_DIR": ".data"}, "AGENCY_DATA_DIR deve essere un percorso assoluto"),
        ({"AGENCY_DATA_DIR": "dati/registro"}, "AGENCY_DATA_DIR deve essere un percorso assoluto"),
        ({"AGENCY_DATA_DIR": "/registro/che/non/esiste"}, "Il registro /registro/che/non/esiste non esiste"),
    ],
)
def test_docker_up_stops_on_an_old_relative_or_missing_data_root(
    tmp_path: Path, variables: dict[str, str], message: str
) -> None:
    """The engine and the server refuse a relative data root (ADR-0045), and Compose would resolve it against
    docker/. An old AGENCY_DATA would be ignored silently. A missing folder would fail the bind mount only
    after both images are built (DX-010). None of them reaches docker."""
    stub = tmp_path / "bin" / "docker"
    stub.parent.mkdir()
    seen = tmp_path / "docker-ran"
    stub.write_text(f'#!/bin/sh\ntouch "{seen}"\n', encoding="utf-8")
    stub.chmod(0o755)
    binary = shutil.which("task")
    if binary is None:
        pytest.fail("Task is not on PATH: it comes from mise.toml, run it with mise active or `mise exec --`")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AGENCY_DATA")}
    environment |= {"PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}"} | variables
    done = subprocess.run(
        [binary, "docker:up"], cwd=REPO_ROOT, env=environment, capture_output=True, text=True
    )
    assert done.returncode != 0
    assert message in done.stdout + done.stderr
    assert not seen.exists()
