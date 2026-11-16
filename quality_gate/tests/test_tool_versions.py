"""Tests of the check that every tool is at its pin (SPEC §8.5)."""

from importlib import metadata
from pathlib import Path

import pytest

from quality_gate.integrity import tool_versions
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file

PYTEST = metadata.version('pytest')


def _codes(root: Path, *requirements: str) -> list[str]:
    listed = ', '.join(f'"{requirement}"' for requirement in requirements)
    write_file(
        root, 'pyproject.toml', f'[dependency-groups]\nquality = [{listed}]\n'
    )
    return [found.code for found in tool_versions.run(root).violations]


def test_matching_pins_pass(tmp_path: Path) -> None:
    """A tool installed at exactly its pin passes.

    Args:
        tmp_path: The repository root.
    """
    assert _codes(tmp_path, f'pytest=={PYTEST}') == []


def test_a_loose_pin_fails(tmp_path: Path) -> None:
    """A pin that allows other versions is not a pin.

    Args:
        tmp_path: The repository root.
    """
    assert _codes(tmp_path, 'pytest>=9') == ['pin-not-exact']


def test_a_missing_package_fails(tmp_path: Path) -> None:
    """A pinned tool that is not installed fails.

    Args:
        tmp_path: The repository root.
    """
    assert _codes(tmp_path, 'no-such-tool==1.0') == ['not-installed']


def test_a_different_version_fails(tmp_path: Path) -> None:
    """A tool installed at another version than its pin fails.

    Args:
        tmp_path: The repository root.
    """
    assert _codes(tmp_path, 'pytest==0.0.1') == ['version-differs']


@pytest.mark.parametrize('config', [None, '[project]\nname = "x"\n'])
def test_a_missing_group_fails(tmp_path: Path, config: str | None) -> None:
    """Without a quality group, or without pyproject.toml, nothing is trusted.

    Args:
        tmp_path: The repository root.
        config: The content of pyproject.toml, or None for no file.
    """
    if config is not None:
        write_file(tmp_path, 'pyproject.toml', config)
    outcome = tool_versions.run(tmp_path)
    assert [found.code for found in outcome.violations] == ['no-quality-group']


def test_the_repository_pins_pass() -> None:
    """Every tool of this repository's quality group is at its pin."""
    root = Path(__file__).resolve().parents[2]
    outcome = tool_versions.run(root)
    assert (outcome.name, outcome.status) == ('tool-versions', Status.PASS)
