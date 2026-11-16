"""The Python files the gate sees (SPEC §7.2).

They are the files git lists, tracked or not but never ignored, that exist
on disk and are Python: `.py`, `.pyi`, or an executable without a suffix
whose first line is a Python shebang. The globs of `exclude` drop the rest.
No folder is listed by hand, so a file in a new folder is seen at once.
"""

import os
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from quality_gate.execution import Runner
from quality_gate.model import GateError

_LISTING = ('ls-files', '-z', '--cached', '--others', '--exclude-standard')
_SUFFIXES = frozenset(('.py', '.pyi'))
# The suffixes a name could have and still be Python, or a Python script.
_MAYBE_PYTHON = _SUFFIXES | {''}
_OUTSIDE_GIT = 'not inside a git repository'


def find_root(runner: Runner) -> Path:
    """Find the top folder of the repository the runner works in.

    Args:
        runner: A runner whose root is any folder inside the repository.

    Returns:
        The repository's top folder.

    Raises:
        GateError: The folder is not inside a git repository.
    """
    completed = runner.git(('rev-parse', '--show-toplevel'))
    if completed.exit_code != 0:
        raise GateError(_OUTSIDE_GIT)
    return Path(completed.stdout.strip())


def discover(runner: Runner, exclude: Sequence[str]) -> tuple[str, ...]:
    """List the Python files of the repository, sorted.

    Args:
        runner: A runner whose root is the repository's top folder.
        exclude: Globs, relative to the root, of the paths to leave out.

    Returns:
        Root-relative POSIX paths.

    Raises:
        GateError: The root is not inside a git repository, or git gave a
            name that is not UTF-8 and could be Python, which would
            otherwise go unseen.
    """
    completed = runner.git(_LISTING)
    if completed.exit_code != 0:
        raise GateError(_OUTSIDE_GIT)
    names = {name for name in completed.stdout.split('\0') if name}
    unreadable = sorted(
        name
        for name in names
        if '\ufffd' in name and PurePosixPath(name).suffix in _MAYBE_PYTHON
    )
    if unreadable:
        message = f'git gave file names that are not UTF-8: {unreadable}'
        raise GateError(message)
    return tuple(
        sorted(
            name
            for name in names
            if _is_python(runner.root / name) and not _excluded(name, exclude)
        ),
    )


def select_given(
    root: Path,
    given: Sequence[str],
    discovered: Sequence[str],
) -> tuple[str, ...]:
    """Keep the discovered files the given paths name, in discovery's order.

    A path is read from the current folder, as a shell would read it. A
    folder stands for every discovered file below it, `.` for all of them.

    Args:
        root: The repository's top folder.
        given: Paths as the user or a hook wrote them.
        discovered: The output of `discover`.

    Returns:
        The discovered files the given paths name, root-relative.
    """
    wanted = {_relative(root, name) for name in given}
    return tuple(
        name
        for name in discovered
        if any(PurePosixPath(name).is_relative_to(path) for path in wanted)
    )


def _relative(root: Path, given: str) -> str:
    path = Path(given).resolve()
    if not path.exists():
        message = f'no such file: {given}'
        raise GateError(message)
    if not path.is_relative_to(root.resolve()):
        message = f'outside the repository: {given}'
        raise GateError(message)
    return path.relative_to(root.resolve()).as_posix()


def _is_python(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix in _SUFFIXES:
        return True
    return not path.suffix and os.access(path, os.X_OK) and _shebang(path)


def _shebang(path: Path) -> bool:
    with path.open('rb') as script:
        first = script.readline()
    return first.startswith(b'#!') and b'python' in first


def _excluded(name: str, exclude: Sequence[str]) -> bool:
    return any(PurePosixPath(name).full_match(glob) for glob in exclude)
