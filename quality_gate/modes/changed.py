"""The mode `changed`: the ratchet (SPEC §7.5).

Every Python file changed since the base, committed or not, tracked or not,
must pass the per-file checks as a whole, not only in the lines touched. The
project checks still read the whole repository; only what touches a changed
file counts. With nothing changed only the integrity checks run, and when
only Markdown or `docs/` changed the suite does not run.
"""

import tempfile
from collections.abc import Sequence
from pathlib import Path

from quality_gate.changes import changed_paths
from quality_gate.checks.per_file import PER_FILE_CHECKS
from quality_gate.checks.project import (
    analyse,
    analyse_changes,
    measure,
    measure_changes,
)
from quality_gate.checks.verdict import CheckInput
from quality_gate.discovery import discover
from quality_gate.execution import Runner
from quality_gate.integrity.guards import Host, run_integrity
from quality_gate.model import CheckResult, Report
from quality_gate.settings import Settings

_WORKSPACE_PREFIX = 'quality-gate-'
_MODE = 'changed'
_DOCS = 'docs/'


def run_changed(
    runner: Runner,
    settings: Settings,
    host: Host,
    *,
    base: str,
) -> Report:
    """Run the ratchet on what changed since `base`.

    Args:
        runner: The runner, rooted in the repository.
        settings: The gate's parameters.
        host: The gate's environment and the user's home.
        base: The reference to compare with, such as `HEAD`.

    Returns:
        The report, whose header names the base.
    """
    discovered = discover(runner, settings.exclude)
    changed = changed_paths(runner, base)
    if changed is not None and not changed:
        return Report(
            mode=_MODE,
            base=base,
            python_files=0,
            checks=run_integrity(runner, discovered, host),
        )
    files = discovered if changed is None else _among(discovered, changed)
    with tempfile.TemporaryDirectory(prefix=_WORKSPACE_PREFIX) as folder:
        checks = (
            *_per_file(runner, files),
            *_project(
                CheckInput(runner=runner, files=discovered),
                Path(folder),
                changed=changed,
                base=base,
            ),
            *run_integrity(runner, discovered, host),
        )
    return Report(
        mode=_MODE,
        base=base,
        python_files=len(files),
        checks=checks,
    )


def _among(
    discovered: Sequence[str],
    changed: Sequence[str],
) -> tuple[str, ...]:
    wanted = frozenset(changed)
    return tuple(name for name in discovered if name in wanted)


def _per_file(
    runner: Runner, files: tuple[str, ...]
) -> tuple[CheckResult, ...]:
    given = CheckInput(runner=runner, files=files)
    return tuple(check(given) for check in PER_FILE_CHECKS)


def _project(
    given: CheckInput,
    workspace: Path,
    *,
    changed: Sequence[str] | None,
    base: str,
) -> tuple[CheckResult, ...]:
    if changed is None:
        # Before the first commit every file is new, so every line must run,
        # and diff-cover has no base to compare with.
        return (
            *analyse(given, workspace),
            *measure(given, workspace),
        )
    analysed = analyse_changes(given, workspace, frozenset(changed))
    if _documentation_only(changed):
        return analysed
    measured = measure_changes(given, workspace, changed=changed, base=base)
    return (*analysed, *measured)


def _documentation_only(changed: Sequence[str]) -> bool:
    return all(
        path.endswith('.md') or path.startswith(_DOCS) for path in changed
    )
