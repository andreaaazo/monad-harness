"""The check `coverage`: what the suite ran, judged from coverage's JSON.

The suite's data (from `tests`) becomes coverage's JSON, XML and text
report. coverage exits 2 below `fail_under = 100`, yet `changed` asks only
that the measured files are the discovered ones (§7.5), so the verdict comes
from the JSON: exits 0 and 2 are both expected (plan B, B5). In `full` every
discovered Python file must be measured, and every line and branch run.
"""

import time
from collections.abc import Iterator, Sequence
from pathlib import Path

from quality_gate.checks.verdict import relative_path
from quality_gate.execution import Completed, Runner, ToolError
from quality_gate.jsonvalue import is_table, load_json
from quality_gate.model import CheckResult, Status, Violation

_COVERAGE = 'coverage'
_EXPECTED = frozenset((0, 2))
_RCFILE = ('--rcfile', 'pyproject.toml')


def run(
    runner: Runner,
    workspace: Path,
    discovered: Sequence[str],
    *,
    whole: bool,
) -> CheckResult:
    """Judge the suite's coverage.

    Args:
        runner: The runner of this run of the gate.
        workspace: The run's temporary folder, where `tests` left its data.
        discovered: The files the gate sees.
        whole: True in `full`, where every line and branch must run.

    Returns:
        The check's result, named `coverage`.
    """
    started = time.perf_counter()
    status, found, raw = _judge(
        runner.with_environment({
            'COVERAGE_FILE': str(workspace / '.coverage')
        }),
        workspace,
        discovered,
        whole=whole,
    )
    return CheckResult(
        _COVERAGE, status, time.perf_counter() - started, found, raw
    )


def _judge(
    runner: Runner,
    workspace: Path,
    discovered: Sequence[str],
    *,
    whole: bool,
) -> tuple[Status, tuple[Violation, ...], str]:
    try:
        measured, raw = _measure(runner, workspace)
    except (OSError, ToolError, ValueError) as error:
        return Status.ERROR, (), str(error)
    found = (
        *_file_sets(measured, discovered, whole=whole),
        *(_not_covered(measured) if whole else ()),
    )
    return (Status.FAIL if found else Status.PASS), found, raw


def _measure(runner: Runner, workspace: Path) -> tuple[dict[str, object], str]:
    report = workspace / 'coverage.json'
    outputs = [
        _expected(runner.tool(_COVERAGE, command))
        for command in (
            ('json', *_RCFILE, '-o', str(report)),
            ('xml', *_RCFILE, '-o', str(workspace / 'coverage.xml')),
            ('report', *_RCFILE),
        )
    ]
    return _files(report, runner.root), outputs[-1].stdout


def _files(report: Path, root: Path) -> dict[str, object]:
    document = load_json(report.read_text(encoding='utf-8'))
    files = document.get('files') if is_table(document) else None
    if not is_table(files):
        message = 'coverage wrote a report with no files'
        raise ValueError(message)
    return {relative_path(root, name): stats for name, stats in files.items()}


def _expected(completed: Completed) -> Completed:
    if completed.exit_code not in _EXPECTED:
        output = f'{completed.stdout}{completed.stderr}'.strip()
        message = f'coverage exited {completed.exit_code}: {output}'
        raise ValueError(message)
    return completed


def _file_sets(
    measured: dict[str, object],
    discovered: Sequence[str],
    *,
    whole: bool,
) -> Iterator[Violation]:
    seen = set(discovered)
    for path in sorted(measured.keys() - seen):
        message = 'measured, but not a file the gate sees'
        yield Violation(path, 1, 1, 'not-discovered', message)
    if whole:
        for path in sorted(seen - measured.keys()):
            if path.endswith('.py'):
                message = 'no test ever imports it'
                yield Violation(path, 1, 1, 'never-imported', message)


def _not_covered(measured: dict[str, object]) -> Iterator[Violation]:
    for path in sorted(measured):
        stats = measured[path]
        lines = stats.get('missing_lines') if is_table(stats) else None
        branches = stats.get('missing_branches') if is_table(stats) else None
        if lines or branches:
            message = f'lines {lines}, branches {branches}'
            yield Violation(path, 1, 1, 'not-covered', message)
