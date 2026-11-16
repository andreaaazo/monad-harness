"""Tests of the lock of the gate's configuration (SPEC §8.3)."""

from pathlib import Path

from quality_gate.integrity import config_lock, lockfile
from quality_gate.jsonvalue import is_table
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file

RUFF = '[tool.ruff.lint.pylint]\nmax-args = 4\nmax-returns = 4\n'
GATE_FILES = ('quality_gate/cli.py',)


def _section(lock: dict[str, object], key: str) -> dict[str, object]:
    found = lock.get(key)
    assert is_table(found)
    return found


def _locked_repository(root: Path) -> None:
    write_file(root, 'pyproject.toml', RUFF)
    write_file(root, 'quality_gate/cli.py', '"""The command line."""\n')
    lock = lockfile.compute_lock(root, GATE_FILES)
    write_file(root, lockfile.LOCK_PATH, lockfile.render_lock(lock))


def _messages(
    root: Path, gate_files: tuple[str, ...] = GATE_FILES
) -> list[str]:
    outcome = config_lock.run(root, gate_files)
    return [found.message for found in outcome.violations]


def test_a_table_hashes_by_its_value(tmp_path: Path) -> None:
    """Spacing, comments and key order do not change a table's hash.

    Args:
        tmp_path: Holds two repositories with the same table.
    """
    write_file(tmp_path, 'one/pyproject.toml', RUFF)
    reordered = (
        '[tool.ruff.lint.pylint]\n'
        '# The same limits, written otherwise.\n'
        'max-returns   =   4\n'
        'max-args = 4\n'
    )
    write_file(tmp_path, 'two/pyproject.toml', reordered)
    hashes = (
        _section(lockfile.compute_lock(tmp_path / name, ()), 'tables')
        for name in ('one', 'two')
    )
    first, second = (tables['tool.ruff'] for tables in hashes)
    assert first == second
    assert first != 'absent'


def test_absent_tables_and_files_are_marked(tmp_path: Path) -> None:
    """A table or file that does not exist is locked as absent.

    Args:
        tmp_path: An empty repository.
    """
    lock = lockfile.compute_lock(tmp_path, ())
    tables, files = _section(lock, 'tables'), _section(lock, 'files')
    assert set(tables) == set(lockfile.LOCKED_TABLES)
    assert set(files) == set(lockfile.LOCKED_FILES)
    assert {*tables.values(), *files.values()} == {'absent'}


def test_the_lock_renders_sorted_with_a_newline() -> None:
    """The lock is JSON with sorted keys, indented, ending with a newline."""
    lock: dict[str, object] = {
        'tables': {'b': 'x', 'a': 'y'},
        'schema': 1,
        'files': {},
    }
    assert lockfile.render_lock(lock) == (
        '{\n'
        '  "files": {},\n'
        '  "schema": 1,\n'
        '  "tables": {\n'
        '    "a": "y",\n'
        '    "b": "x"\n'
        '  }\n'
        '}\n'
    )


def test_a_matching_lock_passes(tmp_path: Path) -> None:
    """A lock written for the current configuration passes.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    outcome = config_lock.run(tmp_path, GATE_FILES)
    assert (outcome.name, outcome.status) == ('config-lock', Status.PASS)


def test_a_changed_threshold_fails(tmp_path: Path) -> None:
    """A threshold changed in a locked table is a difference.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    write_file(
        tmp_path, 'pyproject.toml', RUFF.replace('max-args = 4', 'max-args = 9')
    )
    assert _messages(tmp_path) == ['tables tool.ruff changed']


def test_a_file_added_to_the_gate_fails(tmp_path: Path) -> None:
    """A file added to the gate, or one removed, is a difference.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    added = (*GATE_FILES, 'quality_gate/new.py')
    write_file(tmp_path, 'quality_gate/new.py', '"""New."""\n')
    assert _messages(tmp_path, added) == ['files quality_gate/new.py added']
    assert _messages(tmp_path, ()) == ['files quality_gate/cli.py removed']


def test_the_lock_never_locks_itself(tmp_path: Path) -> None:
    """The lock file is not among the files it locks.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    with_itself = (*GATE_FILES, lockfile.LOCK_PATH)
    assert _messages(tmp_path, with_itself) == []


def test_a_missing_lock_fails(tmp_path: Path) -> None:
    """Without a lock, nothing is locked.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, 'pyproject.toml', RUFF)
    assert _messages(tmp_path) == ['lock missing']


def test_an_unreadable_lock_fails(tmp_path: Path) -> None:
    """A lock that is not a JSON object cannot be compared.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, lockfile.LOCK_PATH, 'not json\n')
    outcome = config_lock.run(tmp_path, GATE_FILES)
    assert [found.code for found in outcome.violations] == ['lock-unreadable']
    write_file(tmp_path, lockfile.LOCK_PATH, '[1]\n')
    assert _messages(tmp_path) == ['the lock is not a JSON object']


def test_a_changed_schema_fails(tmp_path: Path) -> None:
    """A lock of another schema is a difference too.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    lock = lockfile.compute_lock(tmp_path, GATE_FILES)
    write_file(
        tmp_path,
        lockfile.LOCK_PATH,
        lockfile.render_lock({**lock, 'schema': 0}),
    )
    assert _messages(tmp_path) == ['schema changed']


def test_a_normal_dependency_change_passes(tmp_path: Path) -> None:
    """The project's own dependencies stay free to change.

    Args:
        tmp_path: The repository root.
    """
    _locked_repository(tmp_path)
    dependencies = '[project]\ndependencies = ["httpx==1.0"]\n\n'
    write_file(tmp_path, 'pyproject.toml', f'{dependencies}{RUFF}')
    assert _messages(tmp_path) == []
