"""Tests of the suppression scan (SPEC §8.1).

Every sample is written with `~` inside its directive and unmasked at run
time, so this file holds no directive the scan would find.
"""

from pathlib import Path

import pytest

from quality_gate.checks import suppressions
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file


def _unmask(masked: str) -> str:
    return masked.replace('~', '')


def _codes(text: str) -> list[str]:
    return [found.code for found in suppressions.scan_text('a.py', text)]


@pytest.mark.parametrize(
    ('masked', 'code'),
    [
        ('value = 1  # no~qa: E501', 'SUP001'),
        ('value = f()  # type~: ignore[attr-defined]', 'SUP002'),
        ('# pyright~: basic', 'SUP003'),
        ('def f():  # pragma~: no cover', 'SUP004'),
        ('def f():  # pragma~: no branch', 'SUP004'),
        ('def f():  # pragma~: no mutate', 'SUP004'),
        ('# pylint~: disable=duplicate-code', 'SUP005'),
        ('# fmt~: off', 'SUP006'),
        ('import os  # isort~: skip', 'SUP007'),
        ('@pytest.mark~.skipif(True, reason="x")', 'SUP008'),
        ('pytest~.importorskip("numpy")', 'SUP009'),
        ('raise unittest~.SkipTest("x")', 'SUP009'),
        ('collect~_ignore = ["setup.py"]', 'SUP010'),
        ('def pytest~_collection_modifyitems(items): ...', 'SUP010'),
    ],
)
def test_each_directive_is_found(masked: str, code: str) -> None:
    """Each directive of §8.1 is found, with the code of its row.

    Args:
        masked: A line holding the directive, masked with `~`.
        code: The code of the directive's row.
    """
    assert code in _codes(_unmask(masked))


def test_the_match_ignores_case() -> None:
    """Upper case silences a tool just as well, so it is found too."""
    assert _codes(_unmask('value = 1  # NO~QA')) == ['SUP001']


def test_a_directive_inside_a_string_is_found_too() -> None:
    """Some tools read a directive inside a string, so the scan does too."""
    text = _unmask('HELP = "add # type~: ignore to silence it"\n')
    assert _codes(text) == ['SUP002']


def test_the_message_names_who_honours_it() -> None:
    """The message shows the directive and the tools it would silence."""
    found = suppressions.scan_text('a.py', _unmask('# fmt~: off\n'))
    assert [finding.message for finding in found] == [
        _unmask("'fmt~: off' silences ruff format"),
    ]


def test_the_position_is_line_and_column() -> None:
    """With CRLF endings the place is still the directive's line and column."""
    text = _unmask('import os\r\nvalue = 1  # no~qa\r\n')
    assert suppressions.scan_text('src/a.py', text) == (
        Violation(
            path='src/a.py',
            line=2,
            column=14,
            code='SUP001',
            message=_unmask(
                "'no~qa' silences Ruff, flake8, vulture, pydoclint"
            ),
        ),
    )


def test_a_file_that_is_not_utf8_fails(repository: Runner) -> None:
    """A file the scan cannot read is a finding, not a pass.

    Args:
        repository: A fresh repository.
    """
    with (repository.root / 'a.py').open('wb') as written:
        written.writelines((b'\xff',))
    outcome = suppressions.run(CheckInput(runner=repository, files=('a.py',)))
    assert outcome.violations == (
        Violation('a.py', 1, 1, 'SUP000', 'the file is not UTF-8'),
    )


def test_the_scanner_does_not_report_itself() -> None:
    """The scanner's own source holds no directive: none is excused."""
    source = Path(suppressions.__file__).read_text(encoding='utf-8')
    assert suppressions.scan_text('suppressions.py', source) == ()


def test_clean_files_pass(repository: Runner) -> None:
    """Files without a directive pass, with nothing to show.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'a.py', '"""A module."""\n')
    outcome = suppressions.run(CheckInput(runner=repository, files=('a.py',)))
    assert (outcome.name, outcome.status) == ('suppressions', Status.PASS)


def test_run_reads_the_files_from_the_root(repository: Runner) -> None:
    """Each given file is read below the root, and findings name it.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'src/a.py', _unmask('x = 1  # no~qa\n'))
    write_file(repository.root, 'src/b.py', '"""Clean."""\n')
    given = CheckInput(runner=repository, files=('src/a.py', 'src/b.py'))
    outcome = suppressions.run(given)
    assert outcome.status is Status.FAIL
    assert [found.path for found in outcome.violations] == ['src/a.py']
