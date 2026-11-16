"""The modes `full` and `staged` (SPEC §7.5).

`full` runs every check of §7.4 on every discovered file, but the three
that only a change or a commit has: diff-coverage, lock-staged and mutation.
`staged` is the commit hook's mode: the per-file checks on the staged
Python files, then the integrity checks and lock-staged.
"""

import tempfile
from pathlib import Path

from quality_gate.changes import staged_paths
from quality_gate.checks.per_file import PER_FILE_CHECKS
from quality_gate.checks.project import analyse, measure
from quality_gate.checks.verdict import CheckInput
from quality_gate.discovery import discover
from quality_gate.execution import Runner
from quality_gate.integrity import lock_staged
from quality_gate.integrity.guards import Host, run_integrity
from quality_gate.model import Report
from quality_gate.settings import Settings

_WORKSPACE_PREFIX = 'quality-gate-'


def run_full(runner: Runner, settings: Settings, host: Host) -> Report:
    """Run every check that needs no change, on the whole repository.

    The suite's data and the tools' reports go to a temporary folder
    outside the repository, removed when the run ends.

    Args:
        runner: The runner, rooted in the repository.
        settings: The gate's parameters.
        host: The gate's environment and the user's home.

    Returns:
        The report of sixteen checks, in the order of §7.4.
    """
    discovered = discover(runner, settings.exclude)
    given = CheckInput(runner=runner, files=discovered)
    with tempfile.TemporaryDirectory(prefix=_WORKSPACE_PREFIX) as folder:
        workspace = Path(folder)
        checks = (
            *(check(given) for check in PER_FILE_CHECKS),
            *analyse(given, workspace),
            *measure(given, workspace, whole=True),
            *run_integrity(runner, discovered, host),
        )
    return Report(
        mode='full',
        base=None,
        python_files=len(discovered),
        checks=checks,
    )


def run_staged(runner: Runner, settings: Settings, host: Host) -> Report:
    """Run the commit hook's checks on what the next commit holds.

    Args:
        runner: The runner, rooted in the repository.
        settings: The gate's parameters.
        host: The gate's environment and the user's home.

    Returns:
        The report of the per-file checks on the staged Python files, then
        the integrity checks and lock-staged.
    """
    discovered = discover(runner, settings.exclude)
    staged = frozenset(staged_paths(runner))
    files = tuple(name for name in discovered if name in staged)
    given = CheckInput(runner=runner, files=files)
    checks = (
        *(check(given) for check in PER_FILE_CHECKS),
        *run_integrity(runner, discovered, host),
        lock_staged.run(runner, host.environment),
    )
    return Report(
        mode='staged',
        base=None,
        python_files=len(files),
        checks=checks,
    )
