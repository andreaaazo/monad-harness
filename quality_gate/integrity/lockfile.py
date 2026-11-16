"""The lock of the gate's configuration, as a document (SPEC §8.3).

Tables are hashed by their value, so spacing, comments and key order do not
count; files are hashed by their bytes. A table or file that does not exist
is locked as `absent`, so adding one is a difference too.
"""

import hashlib
import json
import tomllib
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

from quality_gate.jsonvalue import is_table

LOCK_PATH: Final = 'quality_gate/config.lock'
LOCKED_TABLES: Final = (
    'tool.ruff',
    'tool.basedpyright',
    'tool.pyright',
    'tool.pydoclint',
    'tool.importlinter',
    'tool.vulture',
    'tool.deptry',
    'tool.pylint',
    'tool.pytest',
    'tool.coverage',
    'tool.mutmut',
    'tool.diff_cover',
    'tool.quality_gate',
    'dependency-groups.quality',
)
LOCKED_FILES: Final = (
    '.flake8',
    '.pre-commit-config.yaml',
    '.claude/settings.json',
    'AGENTS.md',
    'CLAUDE.md',
)
_ABSENT: Final = 'absent'
_SCHEMA: Final = 1


def compute_lock(root: Path, gate_files: Sequence[str]) -> dict[str, object]:
    """Hash the locked tables and files as they are now.

    Args:
        root: The repository root.
        gate_files: The discovered files under `quality_gate/`.

    Returns:
        The lock: its schema, then the hash of each table and file.
    """
    document = _pyproject(root)
    names = (*LOCKED_FILES, *(name for name in gate_files if name != LOCK_PATH))
    return {
        'schema': _SCHEMA,
        'tables': {name: _table_hash(document, name) for name in LOCKED_TABLES},
        'files': {name: _file_hash(root / name) for name in names},
    }


def render_lock(lock: dict[str, object]) -> str:
    """Write a lock as the text of `config.lock`.

    Args:
        lock: A lock from `compute_lock`.

    Returns:
        JSON with sorted keys, indented by two, ending with a newline.
    """
    text = json.dumps(lock, sort_keys=True, indent=2, ensure_ascii=False)
    return f'{text}\n'


def differences(
    old: dict[str, object] | None,
    new: dict[str, object],
) -> tuple[str, ...]:
    """Describe what changed between a stored lock and the current one.

    Args:
        old: The stored lock, or None when there is none.
        new: The lock of the configuration as it is now.

    Returns:
        One line per change, such as `tables tool.ruff changed`.
    """
    if old is None:
        return ('lock missing',)
    schema = (
        () if old.get('schema') == new.get('schema') else ('schema changed',)
    )
    lines = tuple(
        f'{section} {name} {change}'
        for section in ('tables', 'files')
        for name, change in _changes(old.get(section), new.get(section))
    )
    return (*schema, *lines)


def _changes(before: object, after: object) -> Iterator[tuple[str, str]]:
    old: dict[str, object] = before if is_table(before) else {}
    new: dict[str, object] = after if is_table(after) else {}
    for name in sorted(old.keys() | new.keys()):
        if name not in old:
            yield name, 'added'
        elif name not in new:
            yield name, 'removed'
        elif old[name] != new[name]:
            yield name, 'changed'


def _pyproject(root: Path) -> object:
    try:
        document: object = tomllib.loads(
            (root / 'pyproject.toml').read_text(encoding='utf-8'),
        )
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return document


def _table_hash(document: object, name: str) -> str:
    node = document
    for key in name.split('.'):
        node = node.get(key) if is_table(node) else None
    if node is None:
        return _ABSENT
    canonical = json.dumps(
        node,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _file_hash(path: Path) -> str:
    if not path.is_file():
        return _ABSENT
    return hashlib.sha256(path.read_bytes()).hexdigest()
