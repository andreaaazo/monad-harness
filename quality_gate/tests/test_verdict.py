"""Tests of the verdict: a tool's exit code and output become a result."""

from pathlib import Path

import pytest

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    judge,
    relative_path,
    run_tool_check,
)
from quality_gate.execution import Completed, Runner
from quality_gate.jsonvalue import load_json
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_tool

ROOT = Path('/repository')


def _one_per_line(stdout: str, root: Path) -> tuple[Violation, ...]:
    if stdout.startswith('garbled'):
        message = f'cannot read the output under {root}'
        raise ValueError(message)
    return tuple(
        Violation(path=line, line=1, column=1, code='X1', message='found')
        for line in stdout.splitlines()
    )


CHECK = ToolCheck(
    name='fake-check',
    tool='fake',
    options=('--strict',),
    parse=_one_per_line,
    failing=frozenset((1,)),
)


def _judged(
    exit_code: int,
    stdout: str = '',
    stderr: str = '',
) -> tuple[Status, int, str]:
    outcome = judge(CHECK, Completed(exit_code, stdout, stderr, 0.5), ROOT)
    return (outcome.status, len(outcome.violations), outcome.raw)


def _runner(root: Path, scripts: Path) -> Runner:
    return Runner(root=root, scripts=scripts, environment={}, timeout=10)


def test_no_files_pass_without_running_the_tool(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """With no file to check, no tool runs: it would check everything.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder, without the tool, so running it fails.
    """
    given = CheckInput(runner=_runner(tmp_path, scripts), files=())
    outcome = run_tool_check(CHECK, given)
    assert (outcome.status, outcome.violations) == (Status.PASS, ())


def test_exit_zero_with_nothing_reported_passes() -> None:
    """A tool that exits 0 and names nothing passes."""
    assert _judged(0) == (Status.PASS, 0, '')


def test_a_failing_exit_fails_with_the_findings() -> None:
    """A failing exit code with findings fails, and keeps them."""
    assert _judged(1, 'a.py\nb.py\n') == (Status.FAIL, 2, 'a.py\nb.py\n')


def test_a_failing_exit_with_nothing_parsed_fails() -> None:
    """A failure the parser cannot name still fails, with the raw output."""
    assert _judged(1, '', 'it broke') == (Status.FAIL, 0, 'it broke')


def test_exit_zero_with_violations_reported_fails() -> None:
    """A tool that exits 0 but names a finding does not pass."""
    assert _judged(0, 'a.py\n') == (Status.FAIL, 1, 'a.py\n')


def test_an_unexpected_exit_code_is_an_error() -> None:
    """An exit code the check does not expect gives no verdict."""
    assert _judged(2, 'out', 'err') == (Status.ERROR, 0, 'outerr')


def test_output_that_cannot_be_read_is_an_error() -> None:
    """Output the parser refuses gives no verdict, even on exit 0."""
    assert _judged(0, 'garbled') == (Status.ERROR, 0, 'garbled')


def test_a_missing_tool_is_an_error(tmp_path: Path, scripts: Path) -> None:
    """A tool that is not installed is an error, never a pass.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder, without the tool.
    """
    given = CheckInput(runner=_runner(tmp_path, scripts), files=('a.py',))
    outcome = run_tool_check(CHECK, given)
    assert outcome.status is Status.ERROR
    assert outcome.raw.startswith('missing executable:')


def test_files_follow_the_options_as_dot_paths(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """Each file follows the options as `./path`: no name is an option.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    body = (
        'import json, sys\n'
        'sys.stdout.write(json.dumps(sys.argv[1:]))\n'
        'sys.exit(1)\n'
    )
    write_tool(scripts, 'fake', body)
    given = CheckInput(
        runner=_runner(tmp_path, scripts),
        files=('-x.py', 'a b.py'),
    )
    outcome = run_tool_check(CHECK, given)
    arguments = load_json(outcome.raw)
    assert arguments == ['--strict', './-x.py', './a b.py']


@pytest.mark.parametrize(
    'reported',
    ['/repository/src/a.py', './src/a.py', 'src/a.py'],
)
def test_reported_paths_become_root_relative(reported: str) -> None:
    """Absolute, dotted and plain paths all come back root-relative.

    Args:
        reported: A path as a tool printed it.
    """
    assert relative_path(ROOT, reported) == 'src/a.py'


def test_a_path_through_a_linked_root_is_read(tmp_path: Path) -> None:
    """A tool that resolved a linked root still gives a relative path.

    Args:
        tmp_path: Holds the real root and a link to it.
    """
    real = tmp_path / 'real'
    real.mkdir()
    linked = tmp_path / 'linked'
    linked.symlink_to(real)
    reported = str(real / 'src' / 'a.py')
    assert relative_path(linked, reported) == 'src/a.py'


def test_a_path_outside_the_root_cannot_be_read() -> None:
    """A path outside the root is output the gate cannot place."""
    with pytest.raises(ValueError, match='outside the root'):
        pytest.fail(relative_path(ROOT, '/elsewhere/a.py'))
