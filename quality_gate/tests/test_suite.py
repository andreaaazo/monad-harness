"""Tests of the check `tests`: the suite under coverage (SPEC §7.4, §8.6)."""

from pathlib import Path

import pytest

from quality_gate.checks import suite
from quality_gate.execution import Runner, runner_for
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file, write_tool

MODULE = 'def double(number):\n    return number * 2\n'
PASSING = (
    'from pkg.m import double\n'
    '\n'
    '\n'
    'def test_double():\n'
    '    assert double(2) == 4\n'
)


def _project(root: Path, tests: str) -> None:
    write_file(root, 'pyproject.toml', '[tool.coverage.run]\nbranch = true\n')
    write_file(root, 'pkg/__init__.py', '')
    write_file(root, 'pkg/m.py', MODULE)
    write_file(root, 'tests/test_m.py', tests)


def _codes(runner: Runner) -> tuple[Status, list[str]]:
    outcome = suite.run(runner, runner.root.parent)
    return outcome.status, [found.code for found in outcome.violations]


def test_a_passing_suite_passes(repository: Runner) -> None:
    """A suite whose tests all pass, none skipped, passes.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, PASSING)
    outcome = suite.run(repository, repository.root.parent)
    assert (outcome.name, outcome.status) == ('tests', Status.PASS)


def test_a_failing_test_fails_with_its_name(repository: Runner) -> None:
    """A failing test fails the check, and is named.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, PASSING.replace('== 4', '== 5'))
    outcome = suite.run(repository, repository.root.parent)
    assert outcome.status is Status.FAIL
    assert [found.message for found in outcome.violations] == [
        'tests.test_m::test_double',
    ]


def test_a_runtime_skip_fails_the_suite(repository: Runner) -> None:
    """A test skipped at run time fails, with no banned name in sight.

    Args:
        repository: A fresh repository.
    """
    later = (
        'from unittest import SkipTest as Later\n'
        '\n'
        '\n'
        'def test_later():\n'
        "    raise Later('not now')\n"
    )
    _project(repository.root, later)
    assert _codes(repository) == (Status.FAIL, ['skipped'])


def test_an_empty_suite_fails(repository: Runner) -> None:
    """A suite with no test proves nothing.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, '"""No test here."""\n')
    assert _codes(repository) == (Status.FAIL, ['no-tests'])


def test_missing_junit_is_an_error(repository: Runner, scripts: Path) -> None:
    """A run that wrote no JUnit report gives no verdict.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a coverage that writes nothing.
    """
    write_tool(scripts, 'coverage', 'import sys\nsys.exit(0)\n')
    runner = Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=30,
    )
    assert _codes(runner) == (Status.ERROR, [])


def test_unreadable_junit_is_an_error(
    repository: Runner, scripts: Path
) -> None:
    """A JUnit report that is not XML gives no verdict.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a coverage that writes garbage.
    """
    body = (
        'import pathlib, sys\n'
        "pathlib.Path(sys.argv[-1]).write_text('<testsuites><broken')\n"
    )
    write_tool(scripts, 'coverage', body)
    runner = Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=30,
    )
    assert _codes(runner) == (Status.ERROR, [])


def test_pytest_addopts_does_not_reach_pytest(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Options in the caller's PYTEST_ADDOPTS cannot deselect tests.

    Args:
        repository: A fresh repository.
        monkeypatch: Sets PYTEST_ADDOPTS before the runner is built.
    """
    _project(repository.root, PASSING.replace('== 4', '== 5'))
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k nothing')
    runner = runner_for(repository.root, (), 120)
    assert _codes(runner) == (Status.FAIL, ['test-failed'])


def test_coverage_data_lands_in_the_workspace(repository: Runner) -> None:
    """Coverage data goes to the run's folder, never to the repository.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, PASSING)
    workspace = repository.root.parent
    assert suite.run(repository, workspace).status is Status.PASS
    assert (workspace / '.coverage').is_file()
    assert not (repository.root / '.coverage').exists()
