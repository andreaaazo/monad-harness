"""The check `pydoclint`: every argument, return and raise documented."""

import re
from pathlib import Path

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    relative_path,
    run_tool_check,
)
from quality_gate.model import CheckResult, Violation

# One finding, indented under its file: `LINE: CODE: message`.
_FINDING = re.compile(r'\s+(?P<line>\d+): (?P<code>DOC\d+): (?P<message>.*)')


def parse_pydoclint(stdout: str, root: Path) -> tuple[Violation, ...]:
    """Read pydoclint's `--quiet` output into violations.

    Args:
        stdout: What pydoclint wrote, on standard error: a file's path on a
            line of its own, then its findings, each indented; blank lines
            separate the files.
        root: The repository root.

    Returns:
        One violation per finding, at column 1: pydoclint gives none.

    Raises:
        ValueError: A finding has no file above it, or another shape.
    """
    found: list[Violation] = []
    path = ''
    for line in filter(str.strip, stdout.splitlines()):
        if not line[0].isspace():
            path = relative_path(root, line)
            continue
        finding = _FINDING.fullmatch(line)
        if finding is None or not path:
            message = f'pydoclint printed a line the gate cannot read: {line}'
            raise ValueError(message)
        found.append(
            Violation(
                path=path,
                line=int(finding['line']),
                column=1,
                code=finding['code'],
                message=finding['message'],
            ),
        )
    return tuple(found)


CHECK = ToolCheck(
    name='pydoclint',
    tool='pydoclint',
    options=('--config', 'pyproject.toml', '--quiet'),
    parse=parse_pydoclint,
    failing=frozenset((1,)),
    stream='stderr',
)


def run(given: CheckInput) -> CheckResult:
    """Check the docstrings of the given files.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
