"""Tests of the modes `full` and `staged`, and of the command line's grammar."""

from pathlib import Path

import pytest

from quality_gate.command import Command, parse_command
from quality_gate.execution import Runner
from quality_gate.integrity.guards import Host
from quality_gate.model import GateError
from quality_gate.modes.whole import run_full, run_staged
from quality_gate.settings import Settings
from quality_gate.tests.conftest import commit_all
from quality_gate.tests.fakes import PER_FILE_ORDER, write_file, write_tool

SETTINGS = Settings(
    exclude=(),
    env_passthrough=(),
    check_timeout_seconds=60,
    mutation_min_score=0.9,
)
INTEGRITY = ('shadow-config', 'config-lock', 'hook-integrity', 'tool-versions')
PROJECT = (
    'import-contracts',
    'dead-code',
    'dependencies',
    'duplication',
    'tests',
    'coverage',
)
# One fake per tool: each answers as its tool does when it finds nothing.
COVERAGE = (
    'import pathlib, sys\n'
    'command = sys.argv[1]\n'
    "if command == 'run':\n"
    "    junit = sys.argv[sys.argv.index('--junit-xml') + 1]\n"
    '    pathlib.Path(junit).write_text(\n'
    """        '<testsuites><testsuite><testcase classname="t" name="x"/>'\n"""
    """        '</testsuite></testsuites>')\n"""
    "elif command in ('json', 'xml'):\n"
    """    pathlib.Path(sys.argv[-1]).write_text('{"files": {}}')\n"""
)
PYRIGHT = (
    'import sys\n'
    'sys.stdout.write(\'{"generalDiagnostics": [], "summary": '
    '{"filesAnalyzed": 99, "errorCount": 0, "warningCount": 0}}\')\n'
)
DEPTRY = (
    'import pathlib, sys\n'
    "report = sys.argv[sys.argv.index('--json-output') + 1]\n"
    "pathlib.Path(report).write_text('[]')\n"
)
FAKES = (
    ('ruff', "import sys\nsys.stdout.write('[]')\n"),
    ('flake8', ''),
    ('pydoclint', ''),
    ('basedpyright', PYRIGHT),
    ('lint-imports', "print('Contracts: 1 kept, 0 broken.')\n"),
    ('vulture', ''),
    ('deptry', DEPTRY),
    ('pylint', "import sys\nsys.stdout.write('[]')\n"),
    ('coverage', COVERAGE),
)


@pytest.fixture
def faked(repository: Runner) -> Runner:
    """Give a repository whose tools are fakes that find nothing.

    Args:
        repository: A fresh repository.

    Returns:
        A runner rooted in it, whose scripts folder holds the fakes.
    """
    scripts = repository.root.parent / 'fakes'
    scripts.mkdir()
    for name, body in FAKES:
        write_tool(scripts, name, body)
    return Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=60,
    )


def _host(runner: Runner) -> Host:
    return Host(environment={}, home=runner.root.parent)


@pytest.mark.parametrize(
    ('words', 'expected'),
    [
        (['file', 'a.py'], Command('file', ('a.py',), 'text')),
        (['staged'], Command('staged', (), 'text')),
        (['full', '--format', 'json'], Command('full', (), 'json')),
        (['lock'], Command('lock', (), 'text')),
    ],
)
def test_each_mode_parses(words: list[str], expected: Command) -> None:
    """Each mode reads its own arguments, and the format where it has one.

    Args:
        words: The command line after the program.
        expected: What it means.
    """
    assert parse_command(words) == expected


@pytest.mark.parametrize(
    'words',
    [
        ['lock', '--format', 'json'],
        ['full', 'a.py'],
        ['staged', 'a.py'],
        ['lock', 'x'],
    ],
)
def test_a_mode_with_stray_words_is_refused(words: list[str]) -> None:
    """Paths go only to `file`, and `lock` takes nothing at all.

    Args:
        words: A command line a mode does not accept.
    """
    with pytest.raises(GateError, match='usage'):
        pytest.fail(repr(parse_command(words)))


def test_full_runs_every_check_in_order(faked: Runner) -> None:
    """`full` runs every check of §7.4 but diff-coverage and lock-staged.

    Args:
        faked: A repository whose tools are fakes.
    """
    write_file(faked.root, 'src/a.py', '"""A module."""\n')
    report = run_full(faked, SETTINGS, _host(faked))
    names = tuple(check.name for check in report.checks)
    assert names == (*PER_FILE_ORDER, *PROJECT, *INTEGRITY)
    assert (report.mode, report.base, report.python_files) == ('full', None, 1)


def test_staged_checks_only_the_index(faked: Runner) -> None:
    """`staged` checks the staged files and adds lock-staged.

    Args:
        faked: A repository whose tools are fakes.
    """
    for name in ('staged.py', 'unstaged.py'):
        write_file(faked.root, name, '"""A module."""\n')
    commit_all(faked)
    write_file(faked.root, 'staged.py', '"""Changed."""\n')
    write_file(faked.root, 'unstaged.py', '"""Changed too."""\n')
    assert faked.git(('add', 'staged.py')).exit_code == 0
    report = run_staged(faked, SETTINGS, _host(faked))
    names = tuple(check.name for check in report.checks)
    assert names == (*PER_FILE_ORDER, *INTEGRITY, 'lock-staged')
    assert (report.mode, report.python_files) == ('staged', 1)


def test_full_leaves_nothing_in_the_repository(faked: Runner) -> None:
    """The run's temporary files live outside the repository and go.

    Args:
        faked: A repository whose tools are fakes.
    """
    write_file(faked.root, 'src/a.py', '"""A module."""\n')
    before = sorted(path.name for path in Path(faked.root).iterdir())
    assert run_full(faked, SETTINGS, _host(faked)).mode == 'full'
    after = sorted(path.name for path in Path(faked.root).iterdir())
    assert after == before
