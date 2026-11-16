"""The check `ruff-format`: every file as Ruff's formatter would write it."""

from quality_gate.checks.ruff_output import ruff_check
from quality_gate.checks.verdict import CheckInput, run_tool_check
from quality_gate.model import CheckResult

CHECK = ruff_check('ruff-format', ('format', '--check'))


def run(given: CheckInput) -> CheckResult:
    """Check that the given files are formatted.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
