"""Tests of the modes `full`, `staged` and `changed`, and of the grammar."""

from pathlib import Path

import pytest

from quality_gate.command import Command, parse_command
from quality_gate.execution import Runner
from quality_gate.integrity.guards import Host
from quality_gate.model import CheckResult, GateError, Report, Status
from quality_gate.modes.changed import run_changed
from quality_gate.modes.whole import run_full, run_staged
from quality_gate.report import render_text
from quality_gate.settings import Settings
from quality_gate.tests.conftest import commit_all
from quality_gate.tests.fakes import (
    PER_FILE_ORDER,
    with_fakes,
    write_file,
    write_tool,
)

SETTINGS = Settings(
    exclude=(),
    env_passthrough=(),
    check_timeout_seconds=60,
    mutation_min_score=0.9,
)
INTEGRITY = ('shadow-config', 'config-lock', 'hook-integrity', 'tool-versions')
ANALYSES = ('import-contracts', 'dead-code', 'dependencies', 'duplication')
PROJECT = (*ANALYSES, 'tests', 'coverage')
MODULE = '"""A module."""\n'
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
DIFF_COVER = (
    'import pathlib, sys\n'
    "report = sys.argv[-1].removeprefix('json:')\n"
    """pathlib.Path(report).write_text('{"src_stats": {}}')\n"""
)
VULTURE = (
    'print("old.py:1: unused function \'a\' (60% confidence)")\n'
    'print("new.py:1: unused function \'b\' (60% confidence)")\n'
    'raise SystemExit(3)\n'
)
# Names the base it was given, as the file of a changed line it finds.
DIFF_COVER_BASE = (
    'import json, pathlib, sys\n'
    "base = sys.argv[sys.argv.index('--compare-branch') + 1]\n"
    "report = sys.argv[-1].removeprefix('json:')\n"
    "stats = {base + '.py': {'violation_lines': [1]}}\n"
    "pathlib.Path(report).write_text(json.dumps({'src_stats': stats}))\n"
    'raise SystemExit(1)\n'
)
# One block shared by the old file and the new one, placed at the old.
PYLINT_BLOCK = (
    'import json\n'
    "block = 'Similar lines in 2 files', '==old:[0:5]', '==new:[0:5]'\n"
    "found = {'symbol': 'duplicate-code', 'path': 'old.py', 'line': 1}\n"
    "found['message'] = chr(10).join(block)\n"
    'print(json.dumps([found]))\n'
    'raise SystemExit(8)\n'
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
    ('diff-cover', DIFF_COVER),
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
    return with_fakes(repository, scripts)


def _host(runner: Runner) -> Host:
    return Host(environment={}, home=runner.root.parent)


def _changed(runner: Runner) -> Report:
    return run_changed(runner, SETTINGS, _host(runner), base='HEAD')


def _names(report: Report) -> tuple[str, ...]:
    return tuple(check.name for check in report.checks)


def _check(report: Report, name: str) -> CheckResult:
    return next(check for check in report.checks if check.name == name)


def _committed(runner: Runner) -> None:
    write_file(runner.root, 'old.py', MODULE)
    commit_all(runner)


@pytest.mark.parametrize(
    ('words', 'expected'),
    [
        (['file', 'a.py'], Command('file', ('a.py',), 'text')),
        (['staged'], Command('staged', (), 'text')),
        (['full', '--format', 'json'], Command('full', (), 'json')),
        (['lock'], Command('lock', (), 'text')),
        (['changed'], Command('changed', (), 'text', 'HEAD')),
        (
            ['changed', '--base', 'main', '--format', 'json'],
            Command('changed', (), 'json', 'main'),
        ),
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
        ['changed', 'a.py'],
        ['changed', '--base'],
        ['full', '--base', 'main'],
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


def test_nothing_changed_runs_integrity_only(faked: Runner) -> None:
    """With no change, only the four integrity checks run.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    report = _changed(faked)
    assert (_names(report), report.python_files) == (INTEGRITY, 0)


def test_docs_only_skips_the_suite(faked: Runner) -> None:
    """When only Markdown or docs changed, the suite does not run.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    write_file(faked.root, 'README.md', '# Read me\n')
    write_file(faked.root, 'docs/x.md', '# X\n')
    assert _names(_changed(faked)) == (*PER_FILE_ORDER, *ANALYSES, *INTEGRITY)


def test_changed_filters_project_findings(faked: Runner) -> None:
    """A project check's findings count only inside a changed file.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    write_file(faked.root, 'new.py', MODULE)
    write_tool(faked.scripts, 'vulture', VULTURE)
    dead = _check(_changed(faked), 'dead-code')
    assert (dead.status, [found.path for found in dead.violations]) == (
        Status.FAIL,
        ['new.py'],
    )


def test_a_new_top_level_folder_is_seen(faked: Runner) -> None:
    """A file in a folder no list names is checked, with the whole suite.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    write_file(faked.root, 'brand_new/module.py', MODULE)
    report = _changed(faked)
    assert report.python_files == 1
    coverage = _check(report, 'coverage').violations
    assert [(found.path, found.code) for found in coverage] == [
        ('brand_new/module.py', 'never-imported'),
    ]
    assert _names(report) == (
        *PER_FILE_ORDER,
        *PROJECT,
        'diff-coverage',
        *INTEGRITY,
    )


def test_a_deletion_runs_the_suite(faked: Runner) -> None:
    """A deleted module is a change, even beside a Markdown file.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    (faked.root / 'old.py').unlink()
    write_file(faked.root, 'NOTES.md', '# Notes\n')
    report = _changed(faked)
    assert report.python_files == 0
    assert _names(report) == (
        *PER_FILE_ORDER,
        *PROJECT,
        'diff-coverage',
        *INTEGRITY,
    )


def test_the_header_names_the_base(faked: Runner) -> None:
    """The report names the base, and diff-cover compares with it.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    write_file(faked.root, 'new.py', MODULE)
    write_tool(faked.scripts, 'diff-cover', DIFF_COVER_BASE)
    report = run_changed(faked, SETTINGS, _host(faked), base='HEAD~0')
    assert 'base=HEAD~0' in render_text(report).splitlines()[0]
    lines = _check(report, 'diff-coverage').violations
    assert [found.path for found in lines] == ['HEAD~0.py']


def test_a_block_counts_through_its_other_file(faked: Runner) -> None:
    """A duplicate placed in an old file counts when its copy changed.

    Args:
        faked: A repository whose tools are fakes.
    """
    _committed(faked)
    write_file(faked.root, 'new.py', MODULE)
    write_tool(faked.scripts, 'pylint', PYLINT_BLOCK)
    repeated = _check(_changed(faked), 'duplication')
    assert (repeated.status, len(repeated.violations)) == (Status.FAIL, 1)


def test_without_a_commit_everything_has_changed(faked: Runner) -> None:
    """Before the first commit every file is new: coverage is judged whole.

    Args:
        faked: A repository whose tools are fakes.
    """
    write_file(faked.root, 'old.py', MODULE)
    report = _changed(faked)
    assert _names(report) == (*PER_FILE_ORDER, *PROJECT, *INTEGRITY)
    coverage = _check(report, 'coverage')
    assert [found.code for found in coverage.violations] == ['never-imported']
