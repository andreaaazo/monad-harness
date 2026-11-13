"""The settings a test runs with: data and projects under one temporary folder, and no `.env`."""

from __future__ import annotations

from pathlib import Path

from agency.config import Settings


def settings(root: Path, **extra: object) -> Settings:
    return Settings(data_dir=root / "data", projects_dir=root / "projects", _env_file=None, **extra)  # type: ignore[call-arg]
