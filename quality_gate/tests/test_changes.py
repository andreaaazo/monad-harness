"""Tests of git's view of what changed (SPEC §7.2)."""

import os
import shutil

import pytest

from quality_gate.changes import changed_paths, staged_paths
from quality_gate.execution import Runner
from quality_gate.model import GateError
from quality_gate.tests.conftest import commit_all
from quality_gate.tests.fakes import write_file, write_tool

MODULE = '"""A module."""\n'


def _head(runner: Runner) -> str:
    return runner.git(('rev-parse', 'HEAD')).stdout.strip()


def test_untracked_and_unstaged_files_count(repository: Runner) -> None:
    """Staged, unstaged and untracked changes count; deletions do not.

    Args:
        repository: A fresh repository.
    """
    root = repository.root
    for name in ('kept.py', 'edited.py', 'gone.py', 'README.md'):
        write_file(root, name, MODULE)
    commit_all(repository)
    write_file(root, 'edited.py', '"""Edited."""\n')
    write_file(root, 'README.md', '# Edited\n')
    write_file(root, 'staged.py', MODULE)
    assert repository.git(('add', 'staged.py')).exit_code == 0
    write_file(root, 'untracked.py', MODULE)
    (root / 'gone.py').unlink()
    assert changed_paths(repository, 'HEAD') == (
        'README.md',
        'edited.py',
        'staged.py',
        'untracked.py',
    )


def test_the_merge_base_is_the_reference(repository: Runner) -> None:
    """Against an older commit, every commit since it counts.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'first.py', MODULE)
    commit_all(repository)
    base = _head(repository)
    for name in ('second.py', 'third.py'):
        write_file(repository.root, name, MODULE)
        commit_all(repository)
    assert changed_paths(repository, base) == ('second.py', 'third.py')


def test_an_unknown_base_is_a_gate_error(repository: Runner) -> None:
    """A base git cannot resolve is a usage error, named.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'a.py', MODULE)
    commit_all(repository)
    with pytest.raises(GateError, match='unknown base: nowhere'):
        pytest.fail(repr(changed_paths(repository, 'nowhere')))


def test_without_commits_everything_changed(repository: Runner) -> None:
    """In a repository with no commit, everything counts as changed.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'a.py', MODULE)
    assert changed_paths(repository, 'HEAD') is None


def test_staged_paths_are_the_index(repository: Runner) -> None:
    """Only what is staged counts for the commit hook.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'a.py', MODULE)
    commit_all(repository)
    write_file(repository.root, 'a.py', '"""Edited."""\n')
    write_file(repository.root, 'b.py', MODULE)
    assert repository.git(('add', 'b.py')).exit_code == 0
    assert staged_paths(repository) == ('b.py',)


def test_a_failing_listing_is_a_gate_error(repository: Runner) -> None:
    """A listing git could not make never reads as "nothing changed".

    Args:
        repository: A fresh repository, run through a git that fails diff.
    """
    write_file(repository.root, 'a.py', MODULE)
    commit_all(repository)
    real = shutil.which('git')
    shims = repository.root.parent / 'shims'
    shims.mkdir()
    body = (
        'import os, sys\n'
        "if 'diff' in sys.argv:\n"
        "    sys.stderr.write('broken')\n"
        '    sys.exit(128)\n'
        f'os.execv({real!r}, [{real!r}, *sys.argv[1:]])\n'
    )
    write_tool(shims, 'git', body)
    path = f'{shims}{os.pathsep}{repository.environment["PATH"]}'
    broken = repository.with_environment({'PATH': path})
    with pytest.raises(GateError, match='git diff failed: broken'):
        pytest.fail(repr(changed_paths(broken, 'HEAD')))
