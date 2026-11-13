"""The help text of every command, byte for byte (docs/audit/PLAN.md, Task 1.16).

Today argparse takes each description from its module's docstring. Phase 3 translates those docstrings,
and these snapshots prove the operator-facing help stays the same. To accept an intended change, regenerate
them with: UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_help.py
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from agency import cli
from agency.entrypoints.server import schema, serve

SNAPSHOTS = Path(__file__).parent / "snapshots" / "cli"
UPDATE = "UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_help.py"
SUBCOMMANDS = (
    "doctor",
    "verify",
    "migrate",
    "run",
    "resume",
    "decide",
    "budget",
    "report",
    "runs",
    "compare",
    "judge",
    "artifacts",
    "restore",
    "insights",
)
COMMANDS: list[tuple[str, Callable[[list[str]], int], list[str]]] = [
    ("agency", cli.main, []),
    *[(f"agency-{name}", cli.main, [name]) for name in SUBCOMMANDS],
    ("agency-server", serve.main, []),
    ("agency-schemas", schema.main, []),
]


@pytest.mark.parametrize(("name", "main", "arguments"), COMMANDS, ids=[name for name, _, _ in COMMANDS])
def test_cli_help_is_unchanged(
    name: str,
    main: Callable[[list[str]], int],
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("COLUMNS", "100")  # argparse wraps to the terminal width
    with pytest.raises(SystemExit) as stopped:
        main([*arguments, "--help"])
    assert stopped.value.code == 0
    actual = capsys.readouterr().out
    snapshot = SNAPSHOTS / f"{name}.txt"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(actual, encoding="utf-8")
    assert snapshot.is_file(), f"no help snapshot for {name}. If intended: {UPDATE}"
    expected = snapshot.read_text(encoding="utf-8")
    assert actual == expected, f"the help of {name} changed. If intended: {UPDATE}"
