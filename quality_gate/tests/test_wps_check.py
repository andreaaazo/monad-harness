"""Tests of the check of wemake-python-styleguide, through flake8."""

from pathlib import Path

from quality_gate.checks import wps
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
# The directive is written masked, so this file holds none (SPEC §8.1).
SILENCE = '  # no_qa'.replace('_', '')


def _given(runner: Runner, source: str) -> CheckInput:
    write_file(runner.root, '.flake8', '[flake8]\nselect = WPS\n')
    write_file(runner.root, 'src/module.py', source)
    return CheckInput(runner=runner, files=('src/module.py',))


def test_flake8_lines_become_violations() -> None:
    """Each finding line is a violation; every other line is ignored."""
    stdout = (
        './src/a.py:0:1: WPS111 Found too short name: a < 2\n'
        'a line that is no finding\n'
        './src/c.py:1:1: WPS111 Found too short name: x < 2\n'
    )
    assert wps.parse_flake8(stdout, ROOT) == (
        Violation(
            path='src/a.py',
            line=0,
            column=1,
            code='WPS111',
            message='Found too short name: a < 2',
        ),
        Violation(
            path='src/c.py',
            line=1,
            column=1,
            code='WPS111',
            message='Found too short name: x < 2',
        ),
    )


def test_wps_reports_a_real_violation(repository: Runner) -> None:
    """The pinned flake8 and WPS, on a real file, find a short name.

    Args:
        repository: A fresh repository.
    """
    outcome = wps.run(_given(repository, 'x = 1\n'))
    assert outcome.status is Status.FAIL
    assert 'WPS111' in {found.code for found in outcome.violations}


def test_wps_ignores_suppression_comments(repository: Runner) -> None:
    """A suppression comment on the line changes nothing.

    Args:
        repository: A fresh repository.
    """
    outcome = wps.run(_given(repository, f'x = 1{SILENCE}\n'))
    found = {(finding.code, finding.line) for finding in outcome.violations}
    assert ('WPS111', 1) in found
