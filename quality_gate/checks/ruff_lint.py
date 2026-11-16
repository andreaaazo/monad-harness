"""The check `ruff-lint`: Ruff's rules, with no suppression honoured."""

from quality_gate.checks.ruff_output import parse_ruff_json
from quality_gate.checks.verdict import CheckInput, ToolCheck, run_tool_check
from quality_gate.model import CheckResult

# Written masked, so this file holds no directive for the scan (SPEC §8.1).
_IGNORE_DIRECTIVES = '--ignore-no~qa'.replace('~', '')

CHECK = ToolCheck(
    name='ruff-lint',
    tool='ruff',
    options=(
        'check',
        '--config',
        'pyproject.toml',
        '--no-cache',
        '--no-fix',
        _IGNORE_DIRECTIVES,
        '--output-format',
        'json',
    ),
    parse=parse_ruff_json,
    failing=frozenset((1,)),
)


def run(given: CheckInput) -> CheckResult:
    """Run Ruff's rules on the given files.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
