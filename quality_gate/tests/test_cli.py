"""Tests of the command line: the `file` mode and `python -m quality_gate`."""

import logging
import runpy
import sys
from pathlib import Path

import pytest

from quality_gate import cli
from quality_gate.execution import Runner
from quality_gate.jsonvalue import is_table, load_json
from quality_gate.model import CheckResult, Report, Status
from quality_gate.modes import run_file_mode
from quality_gate.settings import Settings
from quality_gate.tests.fakes import write_file, write_tool

ORDER = (
    'ruff-lint',
    'ruff-format',
    'wps',
    'pydoclint',
    'basedpyright',
    'suppressions',
)
SETTINGS = Settings(
    exclude=('legacy/**',),
    env_passthrough=(),
    check_timeout_seconds=30,
    mutation_min_score=0.9,
)
QUIET_PYRIGHT = (
    '{"generalDiagnostics": [], '
    '"summary": {"errorCount": 0, "warningCount": 0}}'
)
CONFIG = (
    '[tool.quality_gate]\n'
    'exclude = []\n'
    'env_passthrough = []\n'
    'check_timeout_seconds = 120\n'
    'mutation_min_score = 0.9\n'
    '\n'
    '[tool.ruff]\n'
    '\n'
    '[tool.pydoclint]\n'
    'style = "google"\n'
    '\n'
    '[tool.basedpyright]\n'
    'typeCheckingMode = "all"\n'
)
MODULE = '"""A module."""\n'
# What each fake tool but Ruff prints when it finds nothing.
CLEAN_OUTPUTS = (
    ('flake8', ''),
    ('pydoclint', ''),
    ('basedpyright', QUIET_PYRIGHT),
)


def _fake(scripts: Path, name: str, stdout: str, *, code: int = 0) -> None:
    body = f'import sys\nsys.stdout.write({stdout!r})\nsys.exit({code})\n'
    write_tool(scripts, name, body)


def _fake_tools(repository: Runner, ruff_exit: int = 0) -> Runner:
    scripts = repository.root.parent / 'scripts'
    scripts.mkdir()
    _fake(scripts, 'ruff', '[]', code=ruff_exit)
    for name, stdout in CLEAN_OUTPUTS:
        _fake(scripts, name, stdout)
    return Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=30,
    )


def _broken(*_arguments: object) -> Report:
    message = 'a bug'
    raise RuntimeError(message)


def _real_repository(
    repository: Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_file(repository.root, 'pyproject.toml', CONFIG)
    write_file(repository.root, '.flake8', '[flake8]\nselect = WPS\n')
    write_file(repository.root, 'src/greeting.py', MODULE)
    monkeypatch.chdir(repository.root)


def test_file_mode_runs_the_six_checks_in_order(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The six per-file checks run, in the order of SPEC §7.4.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
    """
    write_file(repository.root, 'src/a.py', MODULE)
    monkeypatch.chdir(repository.root)
    report = run_file_mode(_fake_tools(repository), SETTINGS, ['src/a.py'])
    assert tuple(check.name for check in report.checks) == ORDER
    assert {check.status for check in report.checks} == {Status.PASS}
    assert (report.mode, report.base, report.python_files) == ('file', None, 1)


def test_every_check_runs_even_after_a_failure(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing check does not stop the ones after it.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
    """
    write_file(repository.root, 'src/a.py', MODULE)
    monkeypatch.chdir(repository.root)
    runner = _fake_tools(repository, ruff_exit=2)
    report = run_file_mode(runner, SETTINGS, ['src/a.py'])
    statuses = [check.status for check in report.checks]
    errors = [Status.ERROR, Status.ERROR]
    passes = [Status.PASS, Status.PASS, Status.PASS, Status.PASS]
    assert statuses == [*errors, *passes]


def test_exit_code_is_zero_only_on_a_pass() -> None:
    """Exit 0 when every check passed, 1 when one did not."""
    passing = Report(mode='file', base=None, python_files=0, checks=())
    assert cli.exit_code(passing) == 0
    failing = Report(
        mode='file',
        base=None,
        python_files=0,
        checks=(CheckResult('x', Status.FAIL, 0, (), ''),),
    )
    assert cli.exit_code(failing) == 1


def test_undiscovered_paths_are_not_checked(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Markdown file and an excluded path are given; no tool runs.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
    """
    write_file(repository.root, 'README.md', '# Read me\n')
    write_file(repository.root, 'legacy/x.py', MODULE)
    monkeypatch.chdir(repository.root)
    runner = _fake_tools(repository, ruff_exit=99)
    given = ['README.md', 'legacy/x.py']
    report = run_file_mode(runner, SETTINGS, given)
    assert report.python_files == 0
    assert {check.status for check in report.checks} == {Status.PASS}


def test_main_prints_the_text_report(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """On a clean file the real tools pass, and the report says so.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
        capsys: Reads what the gate prints.
    """
    _real_repository(repository, monkeypatch)
    assert cli.main(['file', 'src/greeting.py']) == 0
    printed = capsys.readouterr().out
    assert printed.startswith('quality-gate file  python-files=1\n')


def test_main_prints_json_when_asked(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With `--format json` the report is a JSON object.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
        capsys: Reads what the gate prints.
    """
    _real_repository(repository, monkeypatch)
    command = ['file', '--format', 'json', 'src/greeting.py']
    assert cli.main(command) == 0
    document = load_json(capsys.readouterr().out)
    assert is_table(document)
    assert (document['mode'], document['result']) == ('file', 'PASS')


def test_main_outside_a_repository_returns_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Outside git the gate stops with a usage error.

    Args:
        tmp_path: A folder that is no repository.
        monkeypatch: Moves into it.
        capsys: Reads what the gate prints.
    """
    monkeypatch.chdir(tmp_path)
    assert cli.main(['file', 'a.py']) == 2
    assert capsys.readouterr().err.startswith('quality-gate:')


def test_main_with_a_missing_path_returns_two(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A path that does not exist is a usage error, named on stderr.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
        capsys: Reads what the gate prints.
    """
    _real_repository(repository, monkeypatch)
    assert cli.main(['file', 'missing.py']) == 2
    assert 'no such file: missing.py' in capsys.readouterr().err


def test_a_missing_git_returns_two(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without git the gate cannot see the repository: a usage error.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into it and empties PATH.
        capsys: Reads what the gate prints.
    """
    _real_repository(repository, monkeypatch)
    monkeypatch.setenv('PATH', '')
    assert cli.main(['file', 'src/greeting.py']) == 2
    assert 'missing executable: git' in capsys.readouterr().err


def test_an_unexpected_error_returns_two(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug in the gate is logged with its traceback and exits 2.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into it and breaks the file mode.
        caplog: Reads what the gate logs.
    """
    _real_repository(repository, monkeypatch)
    monkeypatch.setattr(cli, 'run_file_mode', _broken)
    with caplog.at_level(logging.ERROR):
        assert cli.main(['file', 'src/greeting.py']) == 2
    assert 'RuntimeError: a bug' in caplog.text


@pytest.mark.parametrize(
    'command',
    [
        [],
        ['full'],
        ['file'],
        ['file', 'a.py', '--format'],
        ['file', 'a.py', '--format', 'xml'],
        ['file', '--verbose', 'a.py'],
    ],
)
def test_a_bad_command_is_a_usage_error(
    command: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mode, a path list or a format the gate does not know exits 2.

    Args:
        command: The arguments after `python -m quality_gate`.
        capsys: Reads what the gate prints.
    """
    assert cli.main(command) == 2
    assert 'usage: python -m quality_gate' in capsys.readouterr().err


def test_python_m_exits_with_the_code_of_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`python -m quality_gate` exits with the code `main` returns.

    Args:
        monkeypatch: Gives the module its command line.
    """
    monkeypatch.setattr(sys, 'argv', ['quality_gate', 'nothing'])
    with pytest.raises(SystemExit, match=r'^2$'):
        pytest.fail(repr(runpy.run_module('quality_gate', run_name='__main__')))
