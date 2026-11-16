"""The check `diff-coverage`: every changed line run by a test, via diff-cover.

diff-cover compares coverage's XML with the changes since the base, the
staged, unstaged and untracked ones included. A line on a branch only partly
run counts as not covered (`--branch-coverage`, §13.6). diff-cover reads a
configuration file only when given `-c`, so none is passed.
"""

from functools import partial
from pathlib import Path

from quality_gate.checks.verdict import ToolCheck, relative_path, run_once
from quality_gate.execution import Runner
from quality_gate.jsonvalue import is_array, is_table, load_json
from quality_gate.model import CheckResult, Violation


def parse_diff_cover(
    _stdout: str,
    root: Path,
    *,
    report: Path,
) -> tuple[Violation, ...]:
    """Read diff-cover's JSON report into one violation per line not run.

    Args:
        _stdout: diff-cover's output; the facts are in `report`.
        root: The repository root.
        report: The JSON file diff-cover wrote.

    Returns:
        One violation per changed line that no test runs.

    Raises:
        ValueError: The report is missing or is not diff-cover's.
    """
    try:
        document = load_json(report.read_text(encoding='utf-8'))
    except OSError as error:
        message = f'diff-cover wrote no report: {error}'
        raise ValueError(message) from error
    stats = document.get('src_stats') if is_table(document) else None
    if not is_table(stats):
        message = 'diff-cover wrote a report the gate cannot read'
        raise ValueError(message)
    return tuple(
        Violation(
            relative_path(root, path),
            line,
            1,
            'diff-coverage',
            'no test runs this changed line',
        )
        for path in sorted(stats)
        for line in _lines(stats[path])
    )


def run(runner: Runner, workspace: Path, base: str) -> CheckResult:
    """Check that every line changed since `base` is run by a test.

    Args:
        runner: The runner of this run of the gate.
        workspace: The run's temporary folder, holding coverage's XML.
        base: The reference the changes are measured from.

    Returns:
        The check's result, named `diff-coverage`.
    """
    report = workspace / 'diff-cover.json'
    check = ToolCheck(
        name='diff-coverage',
        tool='diff-cover',
        options=(
            str(workspace / 'coverage.xml'),
            '--compare-branch',
            base,
            '--fail-under',
            '100',
            '--include-untracked',
            '--branch-coverage',
            '--format',
            f'json:{report}',
        ),
        parse=partial(parse_diff_cover, report=report),
        failing=frozenset((1,)),
    )
    return run_once(check, runner)


def _lines(stats: object) -> tuple[int, ...]:
    lines = stats.get('violation_lines') if is_table(stats) else None
    if not is_array(lines):
        message = 'diff-cover wrote a file without its lines'
        raise ValueError(message)
    return tuple(line for line in lines if isinstance(line, int))
