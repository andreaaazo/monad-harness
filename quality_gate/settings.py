"""The gate's own parameters, read from `[tool.quality_gate]` (SPEC §6.9)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from quality_gate.jsonvalue import is_array, is_table
from quality_gate.model import GateError

_TABLE = '[tool.quality_gate]'


@dataclass(frozen=True, slots=True)
class Settings:
    """The parameters of `[tool.quality_gate]`.

    Attributes:
        exclude: Globs, relative to the root, of paths the gate never sees.
        env_passthrough: Variables the tools receive beyond the fixed ones.
        check_timeout_seconds: The longest one check may run.
        mutation_min_score: The share of mutants the tests must kill.
    """

    exclude: tuple[str, ...]
    env_passthrough: tuple[str, ...]
    check_timeout_seconds: int
    mutation_min_score: float


def load_settings(root: Path) -> Settings:
    """Read the gate's table from the root's `pyproject.toml`.

    A key that is missing is refused like a key of the wrong type: both
    messages name the key.

    Args:
        root: The repository root.

    Returns:
        The parameters, checked.
    """
    table = _table(root / 'pyproject.toml')
    return Settings(
        exclude=_strings(table, 'exclude'),
        env_passthrough=_strings(table, 'env_passthrough'),
        check_timeout_seconds=_seconds(table),
        mutation_min_score=_share(table),
    )


def _table(path: Path) -> dict[str, object]:
    try:
        document: object = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, tomllib.TOMLDecodeError) as error:
        message = f'cannot read {path.name} in {path.parent}: {error}'
        raise GateError(message) from error
    tool = document.get('tool') if is_table(document) else None
    section = tool.get('quality_gate') if is_table(tool) else None
    if not is_table(section):
        message = f'{_TABLE} is missing from {path}'
        raise GateError(message)
    return section


def _invalid(key: str, expected: str) -> GateError:
    return GateError(f'{_TABLE} {key} must be {expected}')


def _strings(table: dict[str, object], key: str) -> tuple[str, ...]:
    candidate = table.get(key)
    if not is_array(candidate):
        raise _invalid(key, 'a list of strings')
    strings = tuple(entry for entry in candidate if isinstance(entry, str))
    if len(strings) != len(candidate):
        raise _invalid(key, 'a list of strings')
    return strings


def _seconds(table: dict[str, object]) -> int:
    key = 'check_timeout_seconds'
    candidate = table.get(key)
    if isinstance(candidate, bool) or not isinstance(candidate, int):
        raise _invalid(key, 'a whole number of seconds')
    if candidate <= 0:
        raise _invalid(key, 'above 0')
    return candidate


def _share(table: dict[str, object]) -> float:
    key = 'mutation_min_score'
    candidate = table.get(key)
    if isinstance(candidate, bool) or not isinstance(candidate, int | float):
        raise _invalid(key, 'a number')
    if not 0 <= candidate <= 1:
        raise _invalid(key, 'between 0 and 1')
    return float(candidate)
