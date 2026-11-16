"""The check `import-contracts`: the architecture's contracts hold (§6.5).

import-linter lays its report out for a terminal: on a narrow one a long
contract name wraps, or runs into its status. The check runs it with
`COLUMNS=1000`, so every contract fits on one line, and trusts the lines
only when their count of broken contracts matches the summary's.
"""

import re
from pathlib import Path

from quality_gate.checks.verdict import ToolCheck, run_once
from quality_gate.execution import Runner
from quality_gate.model import CheckResult, Violation

_STATUS = re.compile(r'(?P<name>.+) (?P<status>KEPT|BROKEN)')
_SUMMARY = re.compile(r'Contracts: \d+ kept, (?P<broken>\d+) broken\.')


def parse_lint_imports(stdout: str, _root: Path) -> tuple[Violation, ...]:
    """Read import-linter's report into one violation per broken contract.

    Args:
        stdout: import-linter's report.
        _root: The repository root; the contracts live in pyproject.toml.

    Returns:
        One violation per broken contract, named by the contract.

    Raises:
        ValueError: The broken lines do not match the summary's count.
    """
    lines = stdout.splitlines()
    statuses = (_STATUS.fullmatch(line) for line in lines)
    broken = tuple(
        Violation('pyproject.toml', 1, 1, 'broken-contract', found['name'])
        for found in statuses
        if found and found['status'] == 'BROKEN'
    )
    counted = [
        int(found['broken'])
        for found in map(_SUMMARY.fullmatch, lines)
        if found
    ]
    if counted != [len(broken)]:
        message = 'import-linter printed a report the gate cannot read'
        raise ValueError(message)
    return broken


CHECK = ToolCheck(
    name='import-contracts',
    tool='lint-imports',
    options=('--no-cache', '--config', 'pyproject.toml'),
    parse=parse_lint_imports,
    failing=frozenset((1,)),
)


def run(runner: Runner) -> CheckResult:
    """Check every contract of `[tool.importlinter]`.

    Args:
        runner: The runner of this run of the gate.

    Returns:
        The check's result.
    """
    return run_once(CHECK, runner.with_environment({'COLUMNS': '1000'}))
