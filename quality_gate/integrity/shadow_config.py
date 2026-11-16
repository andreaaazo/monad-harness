"""The check `shadow-config`: no configuration besides the gate's (§8.2).

The search walks the filesystem, not git's index: a tool reads a file git
ignores just the same. It skips only git's folders and the virtual
environment, and follows no link. A configuration file it cannot read is a
finding too, since its sections cannot be checked.
"""

import configparser
import fnmatch
import time
import tomllib
from collections.abc import Iterator
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
        if not (entry.is_symlink() or entry.name == '.git' or entry == venv):
            yield from _visit(entry, root, venv)


def _visit(entry: Path, root: Path, venv: Path) -> Iterator[Violation]:
    name = entry.relative_to(root).as_posix()
    if entry.is_dir() and entry.name in _FOLDERS:
        yield _found(name, 'shadow-folder', 'a baseline would excuse errors')
    elif entry.is_dir():
        yield from _search(entry, root, venv)
    elif entry.is_file():
        yield from _inspect(entry, name, at_root=entry.parent == root)


def _inspect(path: Path, name: str, *, at_root: bool) -> Iterator[Violation]:
    if path.name in _FILES or (path.name == '.flake8' and not at_root):
        yield _found(name, 'shadow-file', 'a tool would read this file')
    elif path.name == 'pyproject.toml':
        tables = (
            _TABLES_ANYWHERE if at_root else _TABLES_ANYWHERE + _TABLES_BELOW
        )
        yield from _tables(path, name, tables)
    elif path.name in _INI_FILES:
        yield from _sections(path, name)


def _tables(
    path: Path,
    name: str,
    tables: tuple[tuple[str, ...], ...],
) -> Iterator[Violation]:
    try:
        document: object = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        yield _found(name, 'shadow-unreadable', 'its tables cannot be read')
        return
    for keys in tables:
        current = document
        for key in keys:
            current = current.get(key) if is_table(current) else None
        if current is not None:
            table = '.'.join(keys)
            yield _found(name, 'shadow-section', f'[{table}] would be read')


def _sections(path: Path, name: str) -> Iterator[Violation]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, configparser.Error):
        yield _found(name, 'shadow-unreadable', 'its sections cannot be read')
        return
    for section in parser:
        if any(fnmatch.fnmatchcase(section, form) for form in _INI_SECTIONS):
            yield _found(name, 'shadow-section', f'[{section}] would be read')


def _found(path: str, code: str, message: str) -> Violation:
    return Violation(path, 1, 1, code, message)
