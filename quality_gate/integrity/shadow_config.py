"""The check `shadow-config`: no configuration besides the gate's (§8.2).

The search walks the filesystem, not git's index: a tool reads a file git
ignores just the same. It skips only git's folders and the virtual
environment, and never enters a linked folder. A link is judged by its
name, as a tool would follow it, and its content is read only when it
leads to a regular file. A configuration file it cannot read is a finding
too, since its sections cannot be checked.
"""

import configparser
import fnmatch
import time
import tomllib
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Final

from quality_gate.jsonvalue import is_table
from quality_gate.model import CheckResult, Status, Violation

_FILES: Final = frozenset((
    'ruff.toml',
    '.ruff.toml',
    'pyrightconfig.json',
    'basedpyrightconfig.json',
    'pytest.ini',
    '.pytest.ini',
    'pytest.toml',
    '.pytest.toml',
    '.coveragerc',
    'pylintrc',
    '.pylintrc',
    'pylintrc.toml',
    '.pylintrc.toml',
    '.importlinter',
))
_FOLDERS: Final = frozenset(('.basedpyright',))
_INI_FILES: Final = frozenset(('setup.cfg', 'tox.ini'))
_PYPROJECT: Final = 'pyproject.toml'
_READ_FILES: Final = _INI_FILES | {_PYPROJECT}
_UNREADABLE: Final = 'shadow-unreadable'
_SECTION: Final = 'shadow-section'
_found: Final = partial(Violation, line=1, column=1)
_INI_SECTIONS: Final = (
    'flake8',
    'pytest',
    'tool:pytest',
    'coverage:*',
    'pylint*',
    'importlinter*',
    'mutmut',
)
# Forbidden in every pyproject.toml, the root's too.
_TABLES_ANYWHERE: Final = (
    ('tool', 'pyright'),
    ('tool', 'pytest', 'ini_options'),
)
# Forbidden in a pyproject.toml below the root, where Ruff would read it.
_TABLES_BELOW: Final = (('tool', 'ruff'),)


def run(root: Path, venv: Path) -> CheckResult:
    """Search the tree for configuration the tools would read.

    Args:
        root: The repository root.
        venv: The virtual environment, which is skipped.

    Returns:
        The check's result, named `shadow-config`.
    """
    started = time.perf_counter()
    found = tuple(sorted(_search(root, root, venv.resolve())))
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('shadow-config', status, seconds, found, '')


def _search(folder: Path, root: Path, venv: Path) -> Iterator[Violation]:
    for entry in sorted(folder.iterdir()):
        if entry.name != '.git' and entry != venv:
            yield from _visit(entry, root, venv)


def _visit(entry: Path, root: Path, venv: Path) -> Iterator[Violation]:
    name = entry.relative_to(root).as_posix()
    linked = entry.is_symlink()
    if entry.is_dir() and entry.name in _FOLDERS:
        yield _found(
            name, code='shadow-folder', message='a baseline would excuse errors'
        )
    elif entry.is_dir() and not linked:
        yield from _search(entry, root, venv)
    elif linked or entry.is_file():
        yield from _inspect(entry, name, at_root=entry.parent == root)


def _inspect(path: Path, name: str, *, at_root: bool) -> Iterator[Violation]:
    if path.name in _FILES or (path.name == '.flake8' and not at_root):
        yield _found(
            name, code='shadow-file', message='a tool would read this file'
        )
    elif path.name in _READ_FILES:
        yield from _read(path, name, at_root=at_root)


def _read(path: Path, name: str, *, at_root: bool) -> Iterator[Violation]:
    if path.is_file() and path.name == _PYPROJECT:
        tables = (
            _TABLES_ANYWHERE if at_root else _TABLES_ANYWHERE + _TABLES_BELOW
        )
        yield from _tables(path, name, tables)
    elif path.is_file():
        yield from _sections(path, name)
    else:
        # A link to a pipe or a folder: reading it could block the gate.
        yield _found(name, code=_UNREADABLE, message='it leads to no file')


def _tables(
    path: Path,
    name: str,
    tables: tuple[tuple[str, ...], ...],
) -> Iterator[Violation]:
    try:
        document: object = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        yield _found(
            name, code=_UNREADABLE, message='its tables cannot be read'
        )
        return
    for keys in tables:
        current = document
        for key in keys:
            current = current.get(key) if is_table(current) else None
        if current is not None:
            table = '.'.join(keys)
            yield _found(
                name, code=_SECTION, message=f'[{table}] would be read'
            )


def _sections(path: Path, name: str) -> Iterator[Violation]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, configparser.Error):
        yield _found(
            name, code=_UNREADABLE, message='its sections cannot be read'
        )
        return
    for section in parser:
        if any(fnmatch.fnmatchcase(section, form) for form in _INI_SECTIONS):
            yield _found(
                name, code=_SECTION, message=f'[{section}] would be read'
            )
