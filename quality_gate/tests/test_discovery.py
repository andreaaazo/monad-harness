"""Tests of discovery: the Python files the gate sees (SPEC §7.2)."""

import os
import stat
from pathlib import Path

import pytest

from quality_gate.discovery import discover, find_root, select_given
from quality_gate.execution import Runner, runner_for
from quality_gate.model import GateError
from quality_gate.tests.fakes import write_file

PYTHON = '"""A module."""\n'


def _executable(root: Path, name: str) -> None:
    path = root / name
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _found(runner: Runner, *exclude: str) -> tuple[str, ...]:
    return discover(runner, exclude)


def _write_all(root: Path, *names: str) -> None:
    for name in names:
        write_file(root, name, PYTHON)


def test_tracked_and_untracked_files_are_found(repository: Runner) -> None:
    """A file in git's index and one beside it are both seen.

    Args:
        repository: A fresh repository.
    """
    _write_all(repository.root, 'tracked.py', 'untracked.py')
    assert repository.git(('add', 'tracked.py')).exit_code == 0
    assert _found(repository) == ('tracked.py', 'untracked.py')


def test_ignored_files_are_left_out(repository: Runner) -> None:
    """A file git ignores is not the gate's.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, '.gitignore', 'ignored/\n')
    _write_all(repository.root, 'ignored/x.py', 'kept.py')
    assert _found(repository) == ('kept.py',)


def test_a_python_file_in_a_new_folder_is_found(repository: Runner) -> None:
    """No list of folders: a file in a folder made today is seen.

    Args:
        repository: A fresh repository.
    """
    _write_all(repository.root, 'new/deep/x.py')
    assert _found(repository) == ('new/deep/x.py',)


def test_stubs_and_python_scripts_are_found(repository: Runner) -> None:
    """Stubs, and executables with a Python shebang, are Python files.

    Args:
        repository: A fresh repository.
    """
    root = repository.root
    _write_all(root, 'x.pyi')
    write_file(root, 'bin/tool', '#!/usr/bin/env python3\n')
    write_file(root, 'bin/run', '#!/bin/sh\n')
    write_file(root, 'bin/plain', '#!/usr/bin/env python3\n')
    write_file(root, 'README.md', '# Read me\n')
    _executable(root, 'bin/tool')
    _executable(root, 'bin/run')
    assert _found(repository) == ('bin/tool', 'x.pyi')


def test_excluded_globs_are_left_out(repository: Runner) -> None:
    """A glob of `exclude` drops what it matches, and nothing else.

    Args:
        repository: A fresh repository.
    """
    _write_all(repository.root, 'legacy/a/b.py', 'src/legacy.py')
    assert _found(repository, 'legacy/**') == ('src/legacy.py',)


def test_a_deleted_tracked_file_is_left_out(repository: Runner) -> None:
    """A file still in the index but gone from disk is not checked.

    Args:
        repository: A fresh repository.
    """
    _write_all(repository.root, 'gone.py', 'kept.py')
    assert repository.git(('add', 'gone.py')).exit_code == 0
    (repository.root / 'gone.py').unlink()
    assert _found(repository) == ('kept.py',)


def test_spaces_and_accents_are_kept(repository: Runner) -> None:
    """Names with spaces and accents come back as they are on disk.

    Args:
        repository: A fresh repository.
    """
    _write_all(repository.root, 'a b.py', 'è.py')
    assert _found(repository) == ('a b.py', 'è.py')


def test_a_name_that_is_not_utf8_is_a_gate_error(repository: Runner) -> None:
    """A name git cannot give as UTF-8 stops the gate: it would be missed.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, os.fsdecode(b'bad\xff.py'), PYTHON)
    with pytest.raises(GateError, match='UTF-8'):
        pytest.fail(repr(_found(repository)))


def test_find_root_names_the_top_folder(repository: Runner) -> None:
    """From a folder inside the repository, the root is its top folder.

    Args:
        repository: A fresh repository.
    """
    inner = repository.root / 'src' / 'deep'
    inner.mkdir(parents=True)
    root = find_root(runner_for(inner, (), 30))
    assert root.resolve() == repository.root.resolve()


def test_outside_a_repository_is_a_gate_error(tmp_path: Path) -> None:
    """Outside git there is no root and nothing to discover.

    Args:
        tmp_path: A folder that is no repository.
    """
    runner = runner_for(tmp_path, (), 30)
    with pytest.raises(GateError, match='not inside a git repository'):
        pytest.fail(repr(find_root(runner)))
    with pytest.raises(GateError, match='not inside a git repository'):
        pytest.fail(repr(_found(runner)))


def test_given_paths_keep_only_discovered_files(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given paths are normalized, filtered, and ordered like discovery.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository, as the hooks do.
    """
    root = repository.root
    _write_all(root, 'src/a.py', 'src/b.py', 'legacy/x.py')
    write_file(root, 'README.md', '# Read me\n')
    monkeypatch.chdir(root)
    discovered = _found(repository, 'legacy/**')
    given = ('./src/b.py', 'README.md', 'legacy/x.py', str(root / 'src/a.py'))
    assert select_given(root, given, discovered) == ('src/a.py', 'src/b.py')


def test_a_missing_given_path_is_a_gate_error(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path that does not exist is a usage error.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
    """
    monkeypatch.chdir(repository.root)
    with pytest.raises(GateError, match=r'no such file: missing\.py'):
        pytest.fail(repr(select_given(repository.root, ('missing.py',), ())))


def test_a_given_path_outside_is_a_gate_error(
    repository: Runner,
    tmp_path: Path,
) -> None:
    """A file outside the repository is not the gate's to judge.

    Args:
        repository: A fresh repository, inside `tmp_path`.
        tmp_path: The test's folder, which holds a file of its own.
    """
    write_file(tmp_path, 'outside.py', PYTHON)
    outside = str(tmp_path / 'outside.py')
    with pytest.raises(GateError, match='outside the repository'):
        pytest.fail(repr(select_given(repository.root, (outside,), ())))


def test_a_given_folder_selects_the_files_in_it(
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A folder stands for the discovered files below it, `.` for all.

    Args:
        repository: A fresh repository.
        monkeypatch: Moves into the repository.
    """
    _write_all(repository.root, 'src/a.py', 'src/inner/b.py', 'srcx/c.py')
    monkeypatch.chdir(repository.root)
    discovered = discover(repository, ())
    selected = select_given(repository.root, ('src',), discovered)
    assert selected == ('src/a.py', 'src/inner/b.py')
    assert select_given(repository.root, ('.',), discovered) == discovered


def test_a_non_utf8_asset_name_is_ignored(repository: Runner) -> None:
    """A name that is not UTF-8 but cannot be Python does not stop the gate.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, os.fsdecode(b'logo\xff.png'), 'not python')
    _write_all(repository.root, 'a.py')
    assert discover(repository, ()) == ('a.py',)
