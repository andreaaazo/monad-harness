"""The check `dependencies`: the code declares what it imports, via deptry.

deptry reports on the whole tree. The gate keeps only the findings in a
discovered file or in `pyproject.toml`, and drops DEP004 in a test file:
deptry's own default spares only the root `tests/` (plan B, B4). Since the
gate may drop every finding of a run that deptry ended with 1, the verdict
comes from the findings kept: exits 0 and 1 are both expected, and any other
exit, or a report the gate cannot read, is an error.
"""

import dataclasses
from functools import partial
from pathlib import Path, PurePosixPath

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    relative_path,
    run_once,
)
from quality_gate.jsonvalue import is_array, load_json
from quality_gate.model import CheckResult, Status, Violation


def parse_deptry(
    _stdout: str,
    root: Path,
    *,
    report: Path,
    discovered: frozenset[str],
) -> tuple[Violation, ...]:
    """Read deptry's JSON report into the violations the gate keeps.

    Args:
        _stdout: deptry's standard output; the findings are in `report`.
        root: The repository root.
        report: The JSON file deptry wrote.
        discovered: The files the gate sees.

    Returns:
        One violation per finding kept, at its place, or at 1:1 when
        deptry gives none (DEP002 in pyproject.toml).

    Raises:
        ValueError: The report is missing or is not deptry's.
    """
    try:
        document = load_json(report.read_text(encoding='utf-8'))
    except OSError as error:
        message = f'deptry wrote no report: {error}'
        raise ValueError(message) from error
    if not is_array(document):
        message = 'deptry wrote a report the gate cannot read'
        raise ValueError(message)
    found = (_violation(entry, root) for entry in document)
    return tuple(kept for kept in found if _kept(kept, discovered))


def run(given: CheckInput, workspace: Path) -> CheckResult:
    """Check that every import is declared, and every dependency used.

    Args:
        given: The runner and every discovered file.
        workspace: The run's temporary folder, for deptry's report.

    Returns:
        The check's result, named `dependencies`.
    """
    report = workspace / 'deptry.json'
    check = ToolCheck(
        name='dependencies',
        tool='deptry',
        options=(
            '.',
            '--config',
            'pyproject.toml',
            '--no-ansi',
            '--json-output',
            str(report),
        ),
        parse=partial(
            parse_deptry,
            report=report,
            discovered=frozenset(given.files),
        ),
        failing=frozenset((1,)),
    )
    outcome = run_once(check, given.runner)
    if outcome.status is Status.FAIL and not outcome.violations:
        return dataclasses.replace(outcome, status=Status.PASS)
    return outcome


def _violation(entry: object, root: Path) -> Violation:
    match entry:
        case {
            'error': {'code': str(code), 'message': str(message)},
            'location': {
                'file': str(path),
                'line': (int() | None) as line,
                'column': (int() | None) as column,
            },
        }:
            return Violation(
                path=relative_path(root, path),
                line=1 if line is None else line,
                column=1 if column is None else column,
                code=code,
                message=message,
            )
        case _:
            message = f'deptry wrote a finding the gate cannot read: {entry}'
            raise ValueError(message)


def _kept(found: Violation, discovered: frozenset[str]) -> bool:
    place = PurePosixPath(found.path)
    in_tests = 'tests' in place.parts or place.name == 'conftest.py'
    seen = found.path in discovered or found.path == 'pyproject.toml'
    return seen and not (found.code == 'DEP004' and in_tests)
