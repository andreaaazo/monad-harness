"""The four integrity checks of §8, run together in every mode but `file`.

They read the repository's configuration, the hooks and the tools' versions,
none of which a changed Python file can reveal, so `staged`, `full` and
`changed` run them all. `lock` runs three of them as its guards: not
`config-lock`, which a new lock is there to fix.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from quality_gate.execution import Runner
from quality_gate.integrity import (
    config_lock,
    hook_integrity,
    shadow_config,
    tool_versions,
)
from quality_gate.model import CheckResult

_GATE_FOLDER = 'quality_gate/'
_VENV = '.venv'


@dataclass(frozen=True, slots=True)
class Host:
    """What the gate reads from the machine, besides the repository.

    Attributes:
        environment: The gate's own environment, not the tools' cleaned one.
        home: The user's home folder, for Claude Code's user settings.
    """

    environment: Mapping[str, str]
    home: Path


def gate_files(discovered: Sequence[str]) -> tuple[str, ...]:
    """Keep the discovered files of the gate itself, which the lock covers.

    Args:
        discovered: Every discovered Python file.

    Returns:
        The ones under `quality_gate/`.
    """
    return tuple(name for name in discovered if name.startswith(_GATE_FOLDER))


def run_integrity(
    runner: Runner,
    discovered: Sequence[str],
    host: Host,
) -> tuple[CheckResult, ...]:
    """Run the four integrity checks, in the order of §7.4.

    Args:
        runner: A runner rooted in the repository.
        discovered: Every discovered Python file.
        host: The gate's environment and the user's home.

    Returns:
        shadow-config, config-lock, hook-integrity and tool-versions.
    """
    shadow, hooks, versions = run_guards(runner, host)
    locked = config_lock.run(runner.root, gate_files(discovered))
    return shadow, locked, hooks, versions


def run_guards(runner: Runner, host: Host) -> tuple[CheckResult, ...]:
    """Run the checks that must pass before a new lock is written.

    Args:
        runner: A runner rooted in the repository.
        host: The gate's environment and the user's home.

    Returns:
        shadow-config, hook-integrity and tool-versions.
    """
    root = runner.root
    return (
        shadow_config.run(root, root / _VENV),
        hook_integrity.run(
            root,
            host.home,
            runner,
            environment=host.environment,
        ),
        tool_versions.run(root),
    )
