"""What a test must not inherit from the shell that runs pytest."""

from __future__ import annotations

from collections.abc import Iterable

from agency.config import Settings
from agency.contracts.secrets import API_KEY_VARIABLES


def operator_variables(names: Iterable[str]) -> list[str]:
    """The names, among `names`, that change what the engine does: its settings and the API key."""
    prefix = Settings.model_config.get("env_prefix")
    if not prefix:  # an empty prefix would match every name and empty the whole environment
        raise RuntimeError("Settings reads its variables without a prefix: list them here instead")
    return sorted(
        name for name in names if name.upper().startswith(prefix.upper()) or name in API_KEY_VARIABLES
    )
