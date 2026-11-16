"""Tests of the check of pydoclint: complete docstrings (SPEC §6.3)."""

from pathlib import Path

import pytest

from quality_gate.checks import pydoclint
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
# pydoclint 0.11.1's `--quiet` output, cut short.
SAMPLE = (
    'src/a.py\n'
    '    4: DOC101: Function `f`: Docstring contains fewer arguments.\n'
    '    4: DOC203: Function `f` return type(s) not consistent.\n'
    '\n'
    'src/b.py\n'
    '    0: DOC002: Syntax errors; cannot parse this Python file.\n'
)
UNDOCUMENTED = (
    '"""A module."""\n'
    '\n'
    '\n'
    'def double(number: int) -> int:\n'
    '    """Double a number.\n'
    '\n'
    '    Returns:\n'
    '        Twice the number.\n'
    '    """\n'
    '    return number * 2\n'
)


def test_pydoclint_lines_become_violations() -> None:
    """Each indented line is a finding of the file named above it."""
    assert pydoclint.parse_pydoclint(SAMPLE, ROOT) == (
        Violation(
            path='src/a.py',
            line=4,
            column=1,
            code='DOC101',
            message='Function `f`: Docstring contains fewer arguments.',
        ),
        Violation(
            path='src/a.py',
            line=4,
            column=1,
            code='DOC203',
            message='Function `f` return type(s) not consistent.',
        ),
        Violation(
            path='src/b.py',
            line=0,
            column=1,
            code='DOC002',
            message='Syntax errors; cannot parse this Python file.',
        ),
    )


@pytest.mark.parametrize(
    'stdout',
    [
        '    4: DOC101: A finding before any file.\n',
        'src/a.py\n    a finding pydoclint never prints\n',
    ],
)
def test_unreadable_pydoclint_output_is_refused(stdout: str) -> None:
    """A finding with no file above it, or in another shape, is unreadable.

    Args:
        stdout: What a broken or changed pydoclint might print.
    """
    with pytest.raises(ValueError, match='pydoclint'):
        pytest.fail(repr(pydoclint.parse_pydoclint(stdout, ROOT)))


def test_pydoclint_finds_an_undocumented_argument(repository: Runner) -> None:
    """The pinned pydoclint, on a real file, finds an argument left out.

    Args:
        repository: A fresh repository.
    """
    config = '[tool.pydoclint]\nstyle = "google"\n'
    write_file(repository.root, 'pyproject.toml', config)
    write_file(repository.root, 'src/a.py', UNDOCUMENTED)
    outcome = pydoclint.run(CheckInput(runner=repository, files=('src/a.py',)))
    assert outcome.status is Status.FAIL
    assert ('src/a.py', 'DOC101') in {
        (found.path, found.code) for found in outcome.violations
    }
