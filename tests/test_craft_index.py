"""The Craft command index: what the host CLI starts with when the index is loaded."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency.contracts.secrets import API_KEY_VARIABLES
from agency.tools.craft import CommandIndex

# Writes, for each call, its first argument and the variables it was handed, then answers like a Craft CLI.
SPY = """#!/bin/sh
echo "$1 ${{ANTHROPIC_API_KEY:-nessuna}} ${{AGENCY_ANTHROPIC_API_KEY:-nessuna}} ${{HOME:-nessuna}}" \\
  >> "{seen}"
case "$1" in
  --version) echo 'prova-cli 1.2.3' ;;
  commands) echo '[{{"id": "path.create", "label": "Crea un tracciato"}}]' ;;
esac
"""


def test_loading_the_index_hands_the_host_cli_only_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--version` and `commands` run on the host, outside the sandbox. Like the fingerprint's tool versions,
    they start with `PATH` alone: no key, and nothing else from the harness's environment."""
    assert API_KEY_VARIABLES == ("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")  # the names SPY echoes
    bin_dir, seen = tmp_path / "bin", tmp_path / "seen.txt"
    bin_dir.mkdir()
    spy = bin_dir / "prova-cli"
    spy.write_text(SPY.format(seen=seen), encoding="utf-8")
    spy.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    for name in API_KEY_VARIABLES:
        monkeypatch.setenv(name, "sk-ant-prova")
    monkeypatch.setenv("HOME", str(tmp_path))

    index = CommandIndex.load(tmp_path / "cache", app="prova")

    assert list(index.commands) == ["path.create"]
    assert seen.read_text(encoding="utf-8").splitlines() == [
        "--version nessuna nessuna nessuna",
        "commands nessuna nessuna nessuna",
    ]
