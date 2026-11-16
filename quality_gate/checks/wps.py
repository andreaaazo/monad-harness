"""The check `wps`: wemake-python-styleguide, through flake8."""

import re
from pathlib import Path

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    relative_path,
    run_tool_check,
)
from quality_gate.model import CheckResult, Violation

# One finding: `path:line:column: CODE message`.
_FINDING = re.compile(
    r"""
    (?P<path>.+?) : (?P<line>\d+) : (?P<column>\d+) : [ ]
    (?P<code>[A-Z]+\d+) [ ] (?P<message>.*)
    """,
    re.VERBOSE,
)


def parse_flake8(stdout: str, root: Path) -> tuple[Violation, ...]:
    """Read flake8's default format into violations.

    Args:
        stdout: flake8's output, one `path:line:column: CODE message` line
            per finding; every other line is ignored.
        root: The repository root.

    Returns:
        One violation per finding line.
    """
    findings = (_FINDING.fullmatch(line) for line in stdout.splitlines())
    return tuple(
        Violation(
            path=relative_path(root, finding['path']),
            line=int(finding['line']),
            column=int(finding['column']),
            code=finding['code'],
            message=finding['message'],
        )
        for finding in findings
        if finding
    )


CHECK = ToolCheck(
    name='wps',
    tool='flake8',
    options=(
        '--config',
        '.flake8',
        '--disable-noqa',
        '--format',
        'default',
        '--no-show-source',
    ),
    parse=parse_flake8,
    failing=frozenset((1,)),
)


def run(given: CheckInput) -> CheckResult:
    """Run wemake-python-styleguide on the given files.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
