"""The gate's modes, each a run of checks over some files (SPEC §7.5)."""

from collections.abc import Sequence

from quality_gate.checks.per_file import PER_FILE_CHECKS
from quality_gate.checks.verdict import CheckInput
from quality_gate.discovery import discover, select_given
from quality_gate.execution import Runner
from quality_gate.model import Report
from quality_gate.settings import Settings


def run_file_mode(
    runner: Runner,
    settings: Settings,
    given: Sequence[str],
) -> Report:
    """Run the per-file checks on the given paths that are Python files.

    Args:
        runner: The runner, rooted in the repository.
        settings: The gate's parameters.
        given: The paths as the user gave them.

    Returns:
        The report of the six per-file checks.
    """
    discovered = discover(runner, settings.exclude)
    files = select_given(runner.root, given, discovered)
    checked = CheckInput(runner=runner, files=files)
    return Report(
        mode='file',
        base=None,
        python_files=len(files),
        checks=tuple(check(checked) for check in PER_FILE_CHECKS),
    )
