"""The check `ruff-format`: every file as Ruff's formatter would write it."""

from quality_gate.checks.ruff_output import parse_ruff_json
from quality_gate.checks.verdict import CheckInput, ToolCheck, run_tool_check
from quality_gate.model import CheckResult

CHECK = ToolCheck(
    name='ruff-format',
    tool='ruff',
    options=(
        'format',
        '--config',
        'pyproject.toml',
        '--no-cache',
        '--check',
        '--output-format',
        'json',
    ),
    parse=parse_ruff_json,
    failing=frozenset((1,)),
)


def run(given: CheckInput) -> CheckResult:
    """Check that the given files are formatted.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
