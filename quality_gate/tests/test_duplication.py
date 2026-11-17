"""Tests of the check `duplication`, through pylint (SPEC §6.6, §7.4)."""

import json
from pathlib import Path

import pytest

from quality_gate.checks import duplication
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

BLOCK = (
    'def f(x):\n'
    '    a = x + 1\n'
    '    b = a * 2\n'
    '    c = b - 3\n'
    '    d = c / 4\n'
    '    return d\n'
)
CONFIG = (
    '[tool.pylint.main]\n'
    'disable = ["all"]\n'
    'enable = ["duplicate-code"]\n'
    '\n'
    '[tool.pylint.similarities]\n'
    'min-similarity-lines = 4\n'
)
FILES = ('pkg/inner/one.py', 'tests/test_two.py', 'pkg/a.py')


def _layout(root: Path) -> None:
    for name in ('pkg/__init__.py', 'pkg/inner/__init__.py'):
        write_file(root, name, '')
    write_file(root, 'pkg/inner/one.py', BLOCK)
    write_file(root, 'tests/test_two.py', BLOCK)
    write_file(root, 'pkg/a.py', '"""Not a copy."""\n')


def test_module_names_follow_packages(tmp_path: Path) -> None:
    """A module is named from the first folder that is not a package.

    Args:
        tmp_path: The repository root.
    """
    _layout(tmp_path)
    names = [duplication.module_name(path, tmp_path) for path in FILES]
    assert names == ['pkg.inner.one', 'test_two', 'pkg.a']
    assert duplication.module_name('pkg/__init__.py', tmp_path) == 'pkg'


def test_duplicate_blocks_become_violations(tmp_path: Path) -> None:
    """A block is placed at its first file's first line, and names both.

    Args:
        tmp_path: The repository root.
    """
    _layout(tmp_path)
    stdout = json.dumps([
        {
            'symbol': 'duplicate-code',
            'path': 'pkg/a.py',
            'line': 1,
            'message': (
                'Similar lines in 2 files\n'
                '==pkg.inner.one:[1:6]\n'
                '==test_two:[1:6]\n'
                '    a = x + 1\n'
            ),
        },
    ])
    found = duplication.parse_pylint(stdout, tmp_path, files=FILES)
    assert found == (
        Violation(
            path='pkg/inner/one.py',
            line=2,
            column=1,
            code='R0801',
            message=(
                'similar lines in 2 files: pkg/inner/one.py:2-6, '
                'tests/test_two.py:2-6'
            ),
        ),
    )


def test_a_block_touching_a_changed_file_counts(tmp_path: Path) -> None:
    """Every file of a block can be read back, for the ratchet's filter.

    Args:
        tmp_path: The repository root.
    """
    found = Violation(
        path='pkg/inner/one.py',
        line=2,
        column=1,
        code='R0801',
        message=(
            'similar lines in 2 files: pkg/inner/one.py:2-6, '
            'tests/test_two.py:2-6'
        ),
    )
    assert duplication.block_paths(found) == (
        'pkg/inner/one.py',
        'tests/test_two.py',
    )
    assert tmp_path.exists()


def test_a_copied_block_is_found(repository: Runner) -> None:
    """The pinned pylint finds four or more copied lines.

    Args:
        repository: A fresh repository.
    """
    _layout(repository.root)
    write_file(repository.root, 'pyproject.toml', CONFIG)
    outcome = duplication.run(CheckInput(runner=repository, files=FILES))
    assert outcome.status is Status.FAIL
    assert [found.path for found in outcome.violations] == ['pkg/inner/one.py']


def test_unique_code_passes(repository: Runner) -> None:
    """Files that share no block pass.

    Args:
        repository: A fresh repository.
    """
    _layout(repository.root)
    write_file(repository.root, 'pyproject.toml', CONFIG)
    unique = ('pkg/inner/one.py', 'pkg/a.py')
    outcome = duplication.run(CheckInput(runner=repository, files=unique))
    assert (outcome.name, outcome.status) == ('duplication', Status.PASS)


@pytest.mark.parametrize(
    ('files', 'module'),
    [
        (FILES, 'pkg.missing'),
        (('scripts/util.py', 'tools/util.py'), 'util'),
    ],
)
def test_an_unmappable_module_is_refused(
    tmp_path: Path,
    files: tuple[str, ...],
    module: str,
) -> None:
    """A module no file has, or two files share, cannot place a block.

    Args:
        tmp_path: The repository root.
        files: The files pylint read.
        module: The module a block names.
    """
    _layout(tmp_path)
    stdout = json.dumps([
        {
            'symbol': 'duplicate-code',
            'path': 'pkg/a.py',
            'line': 1,
            'message': (
                f'Similar lines in 2 files\n=={module}:[0:5]\n==pkg.a:[0:5]\n'
            ),
        },
    ])
    given = (*files, 'pkg/a.py')
    with pytest.raises(ValueError, match='cannot map'):
        pytest.fail(
            repr(duplication.parse_pylint(stdout, tmp_path, files=given))
        )


@pytest.mark.parametrize(
    'stdout',
    [
        '{}',
        '[{"symbol": "fatal", "message": "x"}]',
        '[{"symbol": "duplicate-code", "message": "no block"}]',
    ],
)
def test_unreadable_pylint_output_is_refused(
    tmp_path: Path,
    stdout: str,
) -> None:
    """Output that is not a list of duplicate blocks cannot be read.

    Args:
        tmp_path: The repository root.
        stdout: What a broken or changed pylint might print.
    """
    with pytest.raises(ValueError, match='pylint printed'):
        pytest.fail(repr(duplication.parse_pylint(stdout, tmp_path, files=())))
