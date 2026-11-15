"""The registry's clock: one rule for every timestamp the studio writes."""

from __future__ import annotations

from datetime import UTC, datetime


def now() -> str:
    """The registry's timestamps: UTC, ISO 8601, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")
