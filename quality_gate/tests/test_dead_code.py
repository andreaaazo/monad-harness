"""Tests of the check `dead-code`, through vulture (SPEC §6.6, §7.4)."""

from pathlib import Path

import pytest

from quality_gate.checks import dead_code
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
CONFIG = '[tool.vulture]\nmin_confidence = 0\n'


def test_vulture_lines_become_violations() -> None:
    """Each line of vulture's report is a violation at its place."""
    stdout = (
        "dead.py:1: unused function 'unused' (60% confidence)\n"
        "./src/a.py:12: unused import 'os' (90% confidence)\n"
    )
    assert dead_code.parse_vulture(stdout, ROOT) == (
        Violation(
            path='dead.py',
            line=1,
            column=1,
            code='dead-code',
            message="unused function 'unused' (60% confidence)",
        ),
        Violation(
            path='src/a.py',
            line=12,
            column=1,
            code='dead-code',
            message="unused import 'os' (90% confidence)",
        ),
    )


def test_a_line_in_another_shape_is_unreadable() -> None:
    """A line vulture never prints means its output changed: unreadable."""
    with pytest.raises(ValueError, match='vulture'):
        pytest.fail(repr(dead_code.parse_vulture('something else\n', ROOT)))


def test_an_unused_function_is_dead_code(repository: Runner) -> None:
    """The pinned vulture finds a function nothing calls.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'pyproject.toml', CONFIG)
    write_file(repository.root, 'dead.py', 'def unused():\n    return 1\n')
    outcome = dead_code.run(CheckInput(runner=repository, files=('dead.py',)))
    assert outcome.status is Status.FAIL
    assert [found.path for found in outcome.violations] == ['dead.py']


def test_used_code_passes(repository: Runner) -> None:
    """A function that is called is not dead.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'pyproject.toml', CONFIG)
    source = 'def used():\n    return 1\n\n\nprint(used())\n'
    write_file(repository.root, 'live.py', source)
    outcome = dead_code.run(CheckInput(runner=repository, files=('live.py',)))
    assert (outcome.name, outcome.status) == ('dead-code', Status.PASS)
