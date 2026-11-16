"""Tests of the two checks of Ruff: lint and format (SPEC §7.4)."""

import json
from pathlib import Path

import pytest

from quality_gate.checks import ruff_format, ruff_lint
from quality_gate.checks.ruff_output import parse_ruff_json
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
# Ruff 0.17.1's JSON, cut to the keys the gate reads.
SAMPLE = """[
  {"code": "D103", "filename": "/repository/src/a.py",
   "location": {"column": 5, "row": 1},
   "message": "Missing docstring in public function"},
  {"code": "invalid-syntax", "filename": "/repository/src/b.py",
   "location": {"column": 12, "row": 1},
   "message": "Expected a parameter or the end of the parameter list"}
]"""
UNDOCUMENTED = 'def answer():\n    return 42\n'
# The directive is written masked, so this file holds none (SPEC §8.1).
SILENCE = '  # no_qa'.replace('_', '')


def _repository_with(runner: Runner, config: str, source: str) -> CheckInput:
    write_file(runner.root, 'pyproject.toml', config)
    write_file(runner.root, 'src/a.py', source)
    return CheckInput(runner=runner, files=('src/a.py',))


def test_ruff_json_becomes_violations() -> None:
    """Each entry of Ruff's JSON is a violation, syntax errors included."""
    assert parse_ruff_json(SAMPLE, ROOT) == (
        Violation(
            path='src/a.py',
            line=1,
            column=5,
            code='D103',
            message='Missing docstring in public function',
        ),
        Violation(
            path='src/b.py',
            line=1,
            column=12,
            code='invalid-syntax',
            message='Expected a parameter or the end of the parameter list',
        ),
    )


@pytest.mark.parametrize(
    'stdout',
    [
        '{"code": "D103"}',
        '[1]',
        '[{"code": "D103", "filename": "a.py", "message": "m"}]',
        json.dumps([
            {
                'code': None,
                'filename': 'a.py',
                'message': 'm',
                'location': {'column': 1, 'row': 1},
            },
        ]),
    ],
)
def test_unreadable_ruff_json_is_refused(stdout: str) -> None:
    """Output that is not Ruff's array of findings cannot be read.

    Args:
        stdout: What a broken or changed Ruff might print.
    """
    with pytest.raises(ValueError, match='Ruff'):
        pytest.fail(repr(parse_ruff_json(stdout, ROOT)))


def test_ruff_lint_reports_a_real_violation(repository: Runner) -> None:
    """The pinned Ruff, on a real file, finds the selected rule.

    Args:
        repository: A fresh repository.
    """
    config = '[tool.ruff.lint]\nselect = ["D103"]\n'
    given = _repository_with(repository, config, UNDOCUMENTED)
    outcome = ruff_lint.run(given)
    assert outcome.status is Status.FAIL
    assert [found.render() for found in outcome.violations] == [
        'src/a.py:1:5 D103 Missing docstring in public function',
    ]


def test_ruff_lint_ignores_suppression_comments(repository: Runner) -> None:
    """A suppression comment on the line changes nothing.

    Args:
        repository: A fresh repository.
    """
    config = '[tool.ruff.lint]\nselect = ["D103"]\n'
    source = UNDOCUMENTED.replace('():', f'():{SILENCE}', 1)
    given = _repository_with(repository, config, source)
    assert ruff_lint.run(given).status is Status.FAIL


def test_ruff_format_reports_an_unformatted_file(repository: Runner) -> None:
    """The pinned Ruff finds a file its formatter would change.

    Args:
        repository: A fresh repository.
    """
    given = _repository_with(repository, '[tool.ruff]\n', 'x=1\n')
    outcome = ruff_format.run(given)
    assert outcome.status is Status.FAIL
    assert [found.code for found in outcome.violations] == ['unformatted']


def test_ruff_format_passes_a_formatted_file(repository: Runner) -> None:
    """A file the formatter would leave alone passes.

    Args:
        repository: A fresh repository.
    """
    given = _repository_with(repository, '[tool.ruff]\n', 'x = 1\n')
    assert ruff_format.run(given).status is Status.PASS
