"""The autouse fixtures every hardening test file imports, so they hold for each of its tests: a data
folder of its own, and a sandbox scope that needs no systemd-run."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency.entrypoints import cli


@pytest.fixture(autouse=True)
def own_data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI command locks its project under the data folder first: keep that out of `.data`."""
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture(autouse=True)
def sandbox_scope_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run`, `resume` and `decide` probe the sandbox scope first: no test of this file spawns systemd-run."""
    monkeypatch.setattr(cli, "scope_problem", lambda: None)
