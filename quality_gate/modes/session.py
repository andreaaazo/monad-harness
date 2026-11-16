"""What every mode works with: the repository, its settings and the host.

The repository is the git repository around the folder the gate starts in.
Its settings come from `[tool.quality_gate]`, and they shape the runner:
which variables the tools see, and how long a tool may run.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from quality_gate.discovery import find_root
from quality_gate.execution import Runner, runner_for
from quality_gate.integrity.guards import Host
from quality_gate.settings import Settings, load_settings

# Enough for `git rev-parse`, the one command run before the settings exist.
_PROBE_SECONDS = 60


@dataclass(frozen=True, slots=True)
class Session:
    """One run of the gate, before its mode runs.

    Attributes:
        runner: The runner, rooted in the repository.
        settings: The gate's parameters.
        host: The gate's environment and the user's home.
    """

    runner: Runner
    settings: Settings
    host: Host


def open_session(folder: Path) -> Session:
    """Find the repository around a folder and read its settings.

    Args:
        folder: Any folder inside the repository.

    Returns:
        The session of this run.
    """
    root = find_root(runner_for(folder, (), _PROBE_SECONDS))
    settings = load_settings(root)
    runner = runner_for(
        root,
        settings.env_passthrough,
        settings.check_timeout_seconds,
    )
    host = Host(environment=os.environ, home=Path.home())
    return Session(runner=runner, settings=settings, host=host)
