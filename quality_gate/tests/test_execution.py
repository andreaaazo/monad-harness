"""Tests of the only module that launches processes."""

import os
import sysconfig
from pathlib import Path

import pytest

from quality_gate.execution import (
    Completed,
    Runner,
    ToolError,
    clean_environment,
    runner_for,
)
from quality_gate.jsonvalue import is_array, load_json
from quality_gate.tests.fakes import write_tool

ECHO_ARGUMENTS = (
    'import json, sys\nsys.stdout.write(json.dumps(sys.argv[1:]))\n'
)


def _runner(root: Path, scripts: Path, timeout: float = 10) -> Runner:
    return Runner(
        root=root,
        scripts=scripts,
        environment=clean_environment(os.environ, ()),
        timeout=timeout,
    )


def _assert_fails(runner: Runner, tool: str, pattern: str) -> None:
    with pytest.raises(ToolError, match=pattern):
        pytest.fail(repr(runner.tool(tool, ())))


def test_tool_runs_in_the_repository_root(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """A tool comes from the scripts folder and works in the root.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    body = 'import os, sys\nsys.stdout.write(os.getcwd())\n'
    write_tool(scripts, 'fake', body)
    completed = _runner(tmp_path, scripts).tool('fake', ())
    assert completed.stdout == str(tmp_path.resolve())


def test_a_tool_never_comes_from_path(tmp_path: Path, scripts: Path) -> None:
    """A tool found only on PATH is missing: PATH could hold anything.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder, empty.
    """
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    write_tool(elsewhere, 'fake', 'import sys\n')
    runner = Runner(
        root=tmp_path,
        scripts=scripts,
        environment={'PATH': f'{elsewhere}{os.pathsep}{os.environ["PATH"]}'},
        timeout=10,
    )
    _assert_fails(runner, 'fake', 'missing executable: .*fake')


def test_a_tool_that_cannot_start_is_a_failure(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """A file the system cannot execute is a failure, not a crash.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    with (scripts / 'fake').open('w', encoding='utf-8') as script:
        script.writelines(('not executable\n',))
    _assert_fails(_runner(tmp_path, scripts), 'fake', 'cannot run .*fake')


def test_exit_code_and_both_streams_are_returned(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """The exit code and both streams come back, with the time it took.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    body = (
        'import sys\n'
        "sys.stdout.write('out')\n"
        "sys.stderr.write('err')\n"
        'sys.exit(3)\n'
    )
    write_tool(scripts, 'fake', body)
    completed = _runner(tmp_path, scripts).tool('fake', ())
    assert completed == Completed(3, 'out', 'err', completed.seconds)
    assert completed.seconds >= 0


def test_arguments_reach_the_tool_unchanged(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """Spaces, accents and a leading dash reach the tool as they are.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    arguments = ['./-x.py', './a b.py', './è.py']
    write_tool(scripts, 'fake', ECHO_ARGUMENTS)
    completed = _runner(tmp_path, scripts).tool('fake', arguments)
    assert load_json(completed.stdout) == arguments


def test_environment_keeps_allowed_variables() -> None:
    """Only the fixed variables and the passthrough ones survive."""
    source = {
        'PATH': '/bin',
        'HOME': '/home/someone',
        'PYTEST_ADDOPTS': '-k nothing',
        'RUFF_CACHE_DIR': '/srv/ruff',
        'PYTHONPATH': '/elsewhere',
        'COVERAGE_RCFILE': '/srv/rc',
        'GIT_DIR': '/srv/git',
        'XDG_RUNTIME_DIR': '/run/user/1000',
    }
    assert clean_environment(source, ('XDG_RUNTIME_DIR',)) == {
        'PATH': '/bin',
        'HOME': '/home/someone',
        'XDG_RUNTIME_DIR': '/run/user/1000',
    }


def test_tool_sees_only_the_cleaned_environment(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """The tool's environment is the runner's, never the caller's.

    The interpreter may add LC_CTYPE by itself when it coerces a C locale.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    body = (
        'import json, os, sys\n'
        'sys.stdout.write(json.dumps(sorted(os.environ)))\n'
    )
    write_tool(scripts, 'fake', body)
    runner = _runner(tmp_path, scripts)
    seen = load_json(runner.tool('fake', ()).stdout)
    added_by_python = {'LC_CTYPE'}
    assert is_array(seen)
    assert set(seen) - added_by_python == set(runner.environment)


def test_a_tool_that_runs_too_long_is_a_failure(
    tmp_path: Path,
    scripts: Path,
) -> None:
    """A tool past its timeout is stopped and becomes a failure.

    Args:
        tmp_path: The repository root.
        scripts: The scripts folder.
    """
    write_tool(scripts, 'fake', 'import time\ntime.sleep(5)\n')
    runner = _runner(tmp_path, scripts, timeout=0.5)
    _assert_fails(runner, 'fake', r'timeout after 0\.5s')


def test_git_comes_from_path(tmp_path: Path, scripts: Path) -> None:
    """Git is no Python package: it comes from the environment's PATH.

    Args:
        tmp_path: The working folder.
        scripts: The scripts folder, empty.
    """
    completed = _runner(tmp_path, scripts).git(['--version'])
    assert completed.stdout.startswith('git version')


@pytest.mark.parametrize('environment', [{}, {'PATH': ''}, {'PATH': 'empty'}])
def test_git_missing_from_path_is_a_failure(
    tmp_path: Path,
    scripts: Path,
    environment: dict[str, str],
) -> None:
    """Without git on PATH, or without PATH, git is a failure.

    Args:
        tmp_path: The working folder.
        scripts: The scripts folder, empty.
        environment: The runner's environment, where `empty` names an
            empty folder.
    """
    empty = tmp_path / 'empty'
    empty.mkdir()
    path = {name: str(empty) for name in environment if environment[name]}
    runner = Runner(
        root=tmp_path,
        scripts=scripts,
        environment={**environment, **path},
        timeout=10,
    )
    with pytest.raises(ToolError, match='missing executable: git'):
        pytest.fail(repr(runner.git(['--version'])))


def test_runner_for_cleans_the_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner takes the interpreter's scripts and a clean environment.

    Args:
        tmp_path: The repository root.
        monkeypatch: Sets a variable that must not reach the tools.
    """
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k nothing')
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/run/user/1000')
    runner = runner_for(tmp_path, ('XDG_RUNTIME_DIR',), 7)
    assert runner.scripts == Path(sysconfig.get_path('scripts'))
    assert 'PYTEST_ADDOPTS' not in runner.environment
    assert runner.environment['XDG_RUNTIME_DIR'] == '/run/user/1000'
    assert (runner.root, runner.timeout) == (tmp_path, 7)
