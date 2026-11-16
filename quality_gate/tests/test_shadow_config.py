"""Tests of the search for configurations the tools would read (§8.2)."""

import os
from pathlib import Path

import pytest

from quality_gate.integrity import shadow_config
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file

SHADOW_FILES = (
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
)


def _found(root: Path) -> list[tuple[str, str]]:
    outcome = shadow_config.run(root, root / '.venv')
    return [(found.path, found.code) for found in outcome.violations]


@pytest.mark.parametrize('name', SHADOW_FILES)
def test_each_shadow_file_is_found(tmp_path: Path, name: str) -> None:
    """A file a tool would read as its configuration is found anywhere.

    Args:
        tmp_path: The repository root.
        name: A forbidden file name.
    """
    write_file(tmp_path, f'deep/{name}', '\n')
    assert _found(tmp_path) == [(f'deep/{name}', 'shadow-file')]


def test_flake8_is_allowed_only_at_the_root(tmp_path: Path) -> None:
    """The root's `.flake8` is the gate's own; any other is a second one.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, '.flake8', '[flake8]\n')
    write_file(tmp_path, 'src/.flake8', '[flake8]\n')
    assert _found(tmp_path) == [('src/.flake8', 'shadow-file')]


def test_a_nested_tool_ruff_table_is_found(tmp_path: Path) -> None:
    """Ruff reads the closest `pyproject.toml` with a `[tool.ruff]` table.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, 'pyproject.toml', '[tool.ruff]\nline-length = 80\n')
    write_file(
        tmp_path, 'pkg/pyproject.toml', '[tool.ruff]\nline-length = 200\n'
    )
    assert _found(tmp_path) == [('pkg/pyproject.toml', 'shadow-section')]


def test_pyright_and_ini_options_tables_are_found(tmp_path: Path) -> None:
    """These two tables are forbidden even in the root's pyproject.toml.

    Args:
        tmp_path: The repository root.
    """
    text = (
        '[tool.pyright]\nstrict = []\n\n'
        '[tool.pytest.ini_options]\naddopts = "-q"\n'
    )
    write_file(tmp_path, 'pyproject.toml', text)
    assert _found(tmp_path) == [
        ('pyproject.toml', 'shadow-section'),
        ('pyproject.toml', 'shadow-section'),
    ]


@pytest.mark.parametrize(
    'section',
    [
        'flake8',
        'pytest',
        'tool:pytest',
        'coverage:run',
        'pylint.main',
        'importlinter',
        'importlinter:contract:one',
        'mutmut',
    ],
)
@pytest.mark.parametrize('name', ['setup.cfg', 'tox.ini'])
def test_setup_cfg_sections_are_found(
    tmp_path: Path,
    name: str,
    section: str,
) -> None:
    """The tools also read their sections in setup.cfg and tox.ini.

    Args:
        tmp_path: The repository root.
        name: The INI file.
        section: A section one of the tools would read.
    """
    write_file(tmp_path, name, f'[{section}]\nkey = value\n')
    assert _found(tmp_path) == [(name, 'shadow-section')]


def test_git_venv_links_and_fifos_are_skipped(tmp_path: Path) -> None:
    """Git's folder, the venv, linked folders and pipes are not read.

    A pipe named pyproject.toml would block the gate if it were read.

    Args:
        tmp_path: The repository root, with a folder outside it to link.
    """
    root = tmp_path / 'repository'
    write_file(root, '.git/ruff.toml', '\n')
    write_file(root, '.venv/lib/ruff.toml', '\n')
    write_file(tmp_path, 'elsewhere/ruff.toml', '\n')
    (root / 'linked').symlink_to(tmp_path / 'elsewhere')
    os.mkfifo(root / 'pyproject.toml')
    assert _found(root) == []


def test_a_baseline_folder_is_found(tmp_path: Path) -> None:
    """The baseline folder of basedpyright would excuse old errors.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, '.basedpyright/baseline.json', '{}\n')
    outcome = shadow_config.run(tmp_path, tmp_path / '.venv')
    assert [(found.path, found.code) for found in outcome.violations] == [
        ('.basedpyright', 'shadow-folder'),
    ]


def test_an_unreadable_config_file_is_found(tmp_path: Path) -> None:
    """A config file the gate cannot read could hide anything.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, 'a/pyproject.toml', 'this is = = not toml\n')
    write_file(tmp_path, 'b/setup.cfg', 'no section header\n')
    assert _found(tmp_path) == [
        ('a/pyproject.toml', 'shadow-unreadable'),
        ('b/setup.cfg', 'shadow-unreadable'),
    ]


def test_a_clean_tree_passes(tmp_path: Path) -> None:
    """The root's own configuration, and INI sections no tool reads, pass.

    Args:
        tmp_path: The repository root.
    """
    write_file(tmp_path, 'pyproject.toml', '[tool.ruff]\n')
    write_file(tmp_path, 'setup.cfg', '[metadata]\nname = x\n')
    write_file(tmp_path, 'src/a.py', '"""A module."""\n')
    outcome = shadow_config.run(tmp_path, tmp_path / '.venv')
    assert (outcome.name, outcome.status) == ('shadow-config', Status.PASS)
