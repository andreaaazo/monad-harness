"""The check `dead-code`: no code that nothing uses, through vulture (§6.6)."""

import re
from pathlib import Path

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    relative_path,
    run_tool_check,
)
from quality_gate.model import CheckResult, Violation

_FINDING = re.compile(r'(?P<path>.+?):(?P<line>\d+): (?P<message>.+)')


def parse_vulture(stdout: str, root: Path) -> tuple[Violation, ...]:
    """Read vulture's report into violations.

    Args:
        stdout: One `path:line: message (N% confidence)` line per finding.
        root: The repository root.

    Returns:
        One violation per finding, at column 1.

    Raises:
        ValueError: A line has another shape.
    """
    found: list[Violation] = []
    for line in filter(str.strip, stdout.splitlines()):
        finding = _FINDING.fullmatch(line)
        if finding is None:
            message = f'vulture printed a line the gate cannot read: {line}'
            raise ValueError(message)
        found.append(
            Violation(
                path=relative_path(root, finding['path']),
                line=int(finding['line']),
                column=1,
                code='dead-code',
                message=finding['message'],
            ),
        )
    return tuple(found)


CHECK = ToolCheck(
    name='dead-code',
    tool='vulture',
    options=('--config', 'pyproject.toml'),
    parse=parse_vulture,
    failing=frozenset((3,)),
)


def run(given: CheckInput) -> CheckResult:
    """Look for dead code in every given file.

    Args:
        given: The runner and every discovered file.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
