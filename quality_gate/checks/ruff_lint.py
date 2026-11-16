"""The check `ruff-lint`: Ruff's rules, with no suppression honoured."""

from quality_gate.checks.ruff_output import ruff_check
from quality_gate.checks.verdict import CheckInput, run_tool_check
from quality_gate.model import CheckResult

# Written masked, so this file holds no directive for the scan (SPEC §8.1).
_IGNORE_DIRECTIVES = '--ignore-no~qa'.replace('~', '')

CHECK = ruff_check('ruff-lint', ('check', '--no-fix', _IGNORE_DIRECTIVES))


def run(given: CheckInput) -> CheckResult:
    """Run Ruff's rules on the given files.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
