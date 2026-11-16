"""Tests of the gate's parameters, read from `[tool.quality_gate]`."""

from pathlib import Path

import pytest

from quality_gate.model import GateError
from quality_gate.settings import Settings, load_settings

LINES = (
    '[tool.quality_gate]',
    'exclude = ["legacy/**"]',
    'env_passthrough = ["XDG_RUNTIME_DIR"]',
    'check_timeout_seconds = 600',
    'mutation_min_score = 0.9',
)


def _write(root: Path, lines: tuple[str, ...]) -> None:
    with (root / 'pyproject.toml').open('w', encoding='utf-8') as config:
        config.writelines(f'{line}\n' for line in lines)


def _assert_refused(root: Path, pattern: str) -> None:
    with pytest.raises(GateError, match=pattern):
        pytest.fail(repr(load_settings(root)))


def _without(key: str) -> tuple[str, ...]:
    return tuple(line for line in LINES if not line.startswith(f'{key} '))


def _with(key: str, toml_value: str) -> tuple[str, ...]:
    return (*_without(key), f'{key} = {toml_value}')


def test_settings_come_from_the_gate_table(tmp_path: Path) -> None:
    """The four keys become the four fields, lists as tuples.

    Args:
        tmp_path: The repository root.
    """
    _write(tmp_path, LINES)
    assert load_settings(tmp_path) == Settings(
        exclude=('legacy/**',),
        env_passthrough=('XDG_RUNTIME_DIR',),
        check_timeout_seconds=600,
        mutation_min_score=0.9,
    )


def test_a_whole_score_is_read_as_a_number(tmp_path: Path) -> None:
    """A score of 1, written without a decimal point, is accepted.

    Args:
        tmp_path: The repository root.
    """
    _write(tmp_path, _with('mutation_min_score', '1'))
    assert load_settings(tmp_path).mutation_min_score == 1


def test_a_missing_file_is_a_gate_error(tmp_path: Path) -> None:
    """Without `pyproject.toml` there are no settings.

    Args:
        tmp_path: The repository root, empty.
    """
    _assert_refused(tmp_path, r'pyproject\.toml')


@pytest.mark.parametrize(
    ('lines', 'named'),
    [
        (('[project]', 'name = "x"'), r'\[tool\.quality_gate\]'),
        (('[tool]', 'quality_gate = 1'), r'\[tool\.quality_gate\]'),
        (('this is not toml',), r'pyproject\.toml'),
        (_without('exclude'), 'exclude'),
        (_without('env_passthrough'), 'env_passthrough'),
        (_without('check_timeout_seconds'), 'check_timeout_seconds'),
        (_without('mutation_min_score'), 'mutation_min_score'),
    ],
)
def test_a_missing_table_or_key_is_a_gate_error(
    tmp_path: Path,
    lines: tuple[str, ...],
    named: str,
) -> None:
    """The error names what is missing, so the fix is obvious.

    Args:
        tmp_path: The repository root.
        lines: The content of `pyproject.toml`.
        named: A pattern the message must contain.
    """
    _write(tmp_path, lines)
    _assert_refused(tmp_path, named)


@pytest.mark.parametrize(
    ('key', 'toml_value'),
    [
        ('exclude', '"x"'),
        ('exclude', '[1]'),
        ('env_passthrough', '["PATH", 2]'),
        ('check_timeout_seconds', '"600"'),
        ('check_timeout_seconds', '0'),
        ('check_timeout_seconds', 'true'),
        ('mutation_min_score', '1.5'),
        ('mutation_min_score', '-0.1'),
        ('mutation_min_score', 'true'),
        ('mutation_min_score', '"0.9"'),
    ],
)
def test_wrong_value_is_a_gate_error(
    tmp_path: Path,
    key: str,
    toml_value: str,
) -> None:
    """A value of the wrong type or out of range is refused, by name.

    Args:
        tmp_path: The repository root.
        key: The key given a wrong value.
        toml_value: The wrong value, as TOML.
    """
    _write(tmp_path, _with(key, toml_value))
    _assert_refused(tmp_path, key)


def test_repository_settings_are_decided() -> None:
    """This repository's table holds the values ADR-0060 decided."""
    root = Path(__file__).resolve().parents[2]
    assert load_settings(root) == Settings(
        exclude=('legacy/**', 'src/agency/qa/scripts/**'),
        env_passthrough=(),
        check_timeout_seconds=600,
        mutation_min_score=0.9,
    )
