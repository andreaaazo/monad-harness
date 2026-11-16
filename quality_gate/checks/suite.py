"""The check `tests`: the whole suite, run under coverage (§7.4, §8.6).

The suite runs as `coverage run -m pytest`, with its data in the run's own
folder and its JUnit report there too. The report decides what a passing
exit code cannot: a suite with no test, or with a test skipped or expected
to fail, does not pass, whatever skipped it.

The report is read with `xml.parsers.expat`, the event parser under
`xml.etree`: Ruff refuses `xml.etree` as a parser of untrusted XML, and this
file is pytest's own, in the gate's temporary folder.
"""

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Final
from xml.parsers import expat

from quality_gate.checks.verdict import ToolCheck, run_once
from quality_gate.execution import Runner
from quality_gate.model import CheckResult, Violation

_FAILED: Final = frozenset(('failure', 'error'))


def parse_junit(
    _stdout: str,
    _root: Path,
    *,
    report: Path,
) -> tuple[Violation, ...]:
    """Read pytest's JUnit report into the violations of §8.6.

    Args:
        _stdout: pytest's output; the facts are in `report`.
        _root: The repository root; the violations sit at `.`.
        report: The JUnit file pytest wrote.

    Returns:
        One violation per failed or skipped test, and one when no test ran.

    Raises:
        ValueError: The report is missing or is not XML.
    """
    reader = _Reader()
    parser = expat.ParserCreate()
    parser.StartElementHandler = reader.start
    try:
        with report.open('rb') as junit:
            parsed = parser.ParseFile(junit)
    except (OSError, expat.ExpatError) as error:
        message = f'pytest wrote no JUnit report the gate can read: {error}'
        raise ValueError(message) from error
    if parsed and not reader.cases:
        reader.found.append(_violation('no-tests', 'pytest ran no test'))
    return tuple(reader.found)


def run(runner: Runner, workspace: Path) -> CheckResult:
    """Run the whole suite under coverage, and judge its report.

    Args:
        runner: The runner of this run of the gate.
        workspace: The run's temporary folder, for coverage's data and
            pytest's JUnit report.

    Returns:
        The check's result, named `tests`.
    """
    report = workspace / 'junit.xml'
    check = ToolCheck(
        name='tests',
        tool='coverage',
        options=(
            'run',
            '--rcfile',
            'pyproject.toml',
            '-m',
            'pytest',
            '-p',
            'no:cacheprovider',
            '--junit-xml',
            str(report),
        ),
        parse=partial(parse_junit, report=report),
        # 1: a test failed; 5: no test was collected, which the report says.
        failing=frozenset((1, 5)),
    )
    coverage_file = {'COVERAGE_FILE': str(workspace / '.coverage')}
    return run_once(check, runner.with_environment(coverage_file))


@dataclass
class _Reader:
    cases: int = 0
    current: str = ''
    found: list[Violation] = field(default_factory=list[Violation])

    def start(self, name: str, attributes: dict[str, str]) -> None:
        if name == 'testcase':
            self.cases += 1
            owner = attributes.get('classname', '')
            test = attributes.get('name', '')
            self.current = f'{owner}::{test}'
        elif name in _FAILED:
            self.found.append(_violation('test-failed', self.current))
        elif name == 'skipped':
            self.found.append(_violation('skipped', self.current))


def _violation(code: str, message: str) -> Violation:
    return Violation('.', 1, 1, code, message)
