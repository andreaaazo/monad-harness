"""Tests of the check `import-contracts` (SPEC §6.5, §7.4)."""

from pathlib import Path

import pytest

from quality_gate.checks import contracts
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
# import-linter 2.15 with COLUMNS=1000, cut short.
SAMPLE = (
    '---------\n'
    'Contracts\n'
    '---------\n'
    '\n'
    'the slices do not import each other (ADR-0021) KEPT\n'
    'no import cycles between sibling modules BROKEN\n'
    '\n'
    'Contracts: 1 kept, 1 broken.\n'
    '\n'
    '----------------\n'
    'Broken contracts\n'
    '----------------\n'
    '\n'
    'no import cycles between sibling modules\n'
    '----------------------------------------\n'
)
# Longer than a terminal's 80 columns, where import-linter would run the name
# into its status: the check's COLUMNS keeps them apart.
LONG_NAME = (
    'no import cycles between the sibling modules of pkg, '
    'at any depth, in any of its folders'
)
CONFIG = (
    '[tool.importlinter]\n'
    'root_package = "pkg"\n'
    '\n'
    '[[tool.importlinter.contracts]]\n'
    f'name = "{LONG_NAME}"\n'
    'type = "acyclic_siblings"\n'
    'ancestors = ["pkg"]\n'
)


def _package(runner: Runner, *, cyclic: bool) -> None:
    write_file(runner.root, 'pyproject.toml', CONFIG)
    write_file(runner.root, 'pkg/__init__.py', '')
    write_file(runner.root, 'pkg/a.py', 'from pkg import b\n')
    write_file(runner.root, 'pkg/b.py', 'from pkg import a\n' if cyclic else '')


def test_broken_contracts_become_violations() -> None:
    """Each broken contract is one violation, named by the contract."""
    assert contracts.parse_lint_imports(SAMPLE, ROOT) == (
        Violation(
            path='pyproject.toml',
            line=1,
            column=1,
            code='broken-contract',
            message='no import cycles between sibling modules',
        ),
    )


@pytest.mark.parametrize(
    'stdout',
    [
        SAMPLE.replace('1 broken', '2 broken'),
        'no summary at all\n',
    ],
)
def test_counts_that_disagree_are_unreadable(stdout: str) -> None:
    """Broken lines that do not add up to the summary cannot be trusted.

    Args:
        stdout: An output whose lines and summary disagree.
    """
    with pytest.raises(ValueError, match='import-linter'):
        pytest.fail(repr(contracts.parse_lint_imports(stdout, ROOT)))


def test_an_import_cycle_breaks_a_contract(repository: Runner) -> None:
    """Two sibling modules importing each other break the contract.

    Args:
        repository: A fresh repository.
    """
    _package(repository, cyclic=True)
    outcome = contracts.run(repository)
    assert outcome.status is Status.FAIL
    assert [found.message for found in outcome.violations] == [LONG_NAME]


def test_kept_contracts_pass(repository: Runner) -> None:
    """Without the cycle every contract is kept.

    Args:
        repository: A fresh repository.
    """
    _package(repository, cyclic=False)
    outcome = contracts.run(repository)
    assert (outcome.name, outcome.status) == ('import-contracts', Status.PASS)
