"""Tests of the check of basedpyright, for types in mode `all` (SPEC §6.4)."""

import json
from pathlib import Path

import pytest

from quality_gate.checks import basedpyright
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file

ROOT = Path('/repository')
ALL_ONLY = '"""A module."""\n\nimport json\n\nVALUE = json.loads("1")\n'


def _diagnostic(
    severity: str, line: int, rule: str | None
) -> dict[str, object]:
    found: dict[str, object] = {
        'file': '/repository/src/a.py',
        'severity': severity,
        'message': f'a {severity}',
        'range': {
            'start': {'line': line, 'character': 4},
            'end': {'line': line, 'character': 5},
        },
    }
    if rule is not None:
        found['rule'] = rule
    return found


def _output(diagnostics: list[object], errors: int, warnings: int) -> str:
    summary = {'errorCount': errors, 'warningCount': warnings}
    return json.dumps({'generalDiagnostics': diagnostics, 'summary': summary})


def test_basedpyright_json_becomes_violations() -> None:
    """Errors and warnings become violations, counted from 1."""
    stdout = _output(
        [
            _diagnostic('error', 12, 'reportAny'),
            _diagnostic('information', 3, 'reportSomething'),
            _diagnostic('warning', 0, None),
        ],
        errors=1,
        warnings=1,
    )
    assert basedpyright.parse_basedpyright(stdout, ROOT) == (
        Violation('src/a.py', 13, 5, 'reportAny', 'a error'),
        Violation('src/a.py', 1, 5, 'basedpyright', 'a warning'),
    )


def test_a_count_without_diagnostics_still_fails() -> None:
    """A summary that counts errors it did not list is still a finding."""
    stdout = _output([], errors=2, warnings=0)
    found = basedpyright.parse_basedpyright(stdout, ROOT)
    assert [(finding.path, finding.code) for finding in found] == [
        ('.', 'summary'),
    ]


@pytest.mark.parametrize(
    'stdout',
    [
        '[]',
        json.dumps({'generalDiagnostics': []}),
        json.dumps({'generalDiagnostics': {}, 'summary': {}}),
        _output([1], errors=1, warnings=0),
        json.dumps({'generalDiagnostics': [], 'summary': {'errorCount': 1}}),
        _output([{'severity': 'error'}], errors=1, warnings=0),
    ],
)
def test_unreadable_basedpyright_json_is_refused(stdout: str) -> None:
    """Output that is not basedpyright's report cannot be read.

    Args:
        stdout: What a broken or changed basedpyright might print.
    """
    with pytest.raises(ValueError, match='basedpyright'):
        pytest.fail(repr(basedpyright.parse_basedpyright(stdout, ROOT)))


def test_basedpyright_reports_a_real_error(repository: Runner) -> None:
    """The pinned basedpyright, in mode `all`, refuses an `Any`.

    Args:
        repository: A fresh repository.
    """
    config = '[tool.basedpyright]\ntypeCheckingMode = "all"\n'
    write_file(repository.root, 'pyproject.toml', config)
    write_file(repository.root, 'src/a.py', ALL_ONLY)
    given = CheckInput(runner=repository, files=('src/a.py',))
    outcome = basedpyright.run(given)
    assert outcome.status is Status.FAIL
    assert 'reportAny' in {found.code for found in outcome.violations}


def test_basedpyright_reads_its_project_file(repository: Runner) -> None:
    """The project file wins over a pyrightconfig.json beside it.

    Until the switch this repository holds both (DEVIATIONS 1).

    Args:
        repository: A fresh repository.
    """
    basic = '{"typeCheckingMode": "basic"}\n'
    write_file(repository.root, 'pyrightconfig.json', basic)
    config = '[tool.basedpyright]\ntypeCheckingMode = "all"\n'
    write_file(repository.root, 'pyproject.toml', config)
    write_file(repository.root, 'src/a.py', ALL_ONLY)
    given = CheckInput(runner=repository, files=('src/a.py',))
    assert basedpyright.run(given).status is Status.FAIL


def test_a_clean_file_passes(repository: Runner) -> None:
    """A file with nothing to say passes, so the check can pass at all.

    Args:
        repository: A fresh repository.
    """
    config = '[tool.basedpyright]\ntypeCheckingMode = "all"\n'
    write_file(repository.root, 'pyproject.toml', config)
    write_file(repository.root, 'src/a.py', '"""A module."""\n')
    given = CheckInput(runner=repository, files=('src/a.py',))
    assert basedpyright.run(given).status is Status.PASS
