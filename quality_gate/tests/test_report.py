"""Tests of the report, as text and as JSON (SPEC §7.6)."""

from quality_gate.jsonvalue import load_json
from quality_gate.model import CheckResult, Report, Status, Violation
from quality_gate.report import render_json, render_text

MISSING_DOCSTRING = Violation(
    path='src/a.py',
    line=3,
    column=1,
    code='D103',
    message='Missing docstring in public function',
)
LONG_LINE = Violation(
    path='src/b.py',
    line=1,
    column=1,
    code='E501',
    message='Line too long',
)


def _check(
    name: str,
    status: Status,
    violations: tuple[Violation, ...] = (),
) -> CheckResult:
    return CheckResult(
        name=name,
        status=status,
        seconds=0.08,
        violations=violations,
        raw='',
    )


def _report(*checks: CheckResult, base: str | None = None) -> Report:
    return Report(mode='file', base=base, python_files=3, checks=checks)


def _failing_report() -> Report:
    lint = CheckResult(
        name='ruff-lint',
        status=Status.FAIL,
        seconds=0.41,
        violations=(LONG_LINE, MISSING_DOCSTRING),
        raw='[...]',
    )
    types = CheckResult(
        name='basedpyright',
        status=Status.ERROR,
        seconds=600,
        violations=(),
        raw='timeout after 600s',
    )
    return _report(lint, _check('ruff-format', Status.PASS), types)


def test_text_report_has_table_and_details() -> None:
    """Header, one row per check, the result, then what did not pass."""
    assert render_text(_failing_report()) == (
        'quality-gate file  python-files=3\n'
        'CHECK             STATUS  COUNT  SECONDS\n'
        'ruff-lint         FAIL        2     0.41\n'
        'ruff-format       PASS        0     0.08\n'
        'basedpyright      ERROR       -   600.00\n'
        'RESULT: FAIL  failed=1  errors=1  checks=3\n'
        '\n'
        '== ruff-lint (2) ==\n'
        'src/a.py:3:1 D103 Missing docstring in public function\n'
        'src/b.py:1:1 E501 Line too long\n'
        '== basedpyright (ERROR) ==\n'
        'timeout after 600s\n'
    )


def test_the_header_names_the_base() -> None:
    """The mode `changed` compares with a base, and the header says which."""
    report = Report(mode='changed', base='HEAD', python_files=3, checks=())
    header = render_text(report).splitlines()[0]
    assert header == 'quality-gate changed  base=HEAD  python-files=3'


def test_violations_sort_by_path_then_line() -> None:
    """Lines sort as numbers: line 2 before line 10, then the next file."""
    found = tuple(
        Violation(path=path, line=line, column=1, code='X1', message='m')
        for path, line in (('b.py', 1), ('a.py', 10), ('a.py', 2))
    )
    report = _report(_check('ruff-lint', Status.FAIL, found))
    details = render_text(report).splitlines()[-3:]
    assert details == ['a.py:2:1 X1 m', 'a.py:10:1 X1 m', 'b.py:1:1 X1 m']


def test_a_bare_failure_shows_the_raw_output() -> None:
    """A tool that failed without a readable finding shows its own words."""
    bare = CheckResult(
        name='wps',
        status=Status.FAIL,
        seconds=1,
        violations=(),
        raw='flake8: something broke\n',
    )
    details = render_text(_report(bare)).splitlines()[-2:]
    assert details == ['== wps (0) ==', 'flake8: something broke']


def test_a_passing_report_ends_at_its_result_line() -> None:
    """Nothing follows the result line when every check passed."""
    text = render_text(_report(_check('ruff-lint', Status.PASS)))
    assert text.endswith('RESULT: PASS  failed=0  errors=0  checks=1\n')


def test_the_json_report_carries_every_field() -> None:
    """The JSON report holds the same facts, violations sorted."""
    document = load_json(render_json(_failing_report()))
    lint: dict[str, object] = {
        'name': 'ruff-lint',
        'status': 'FAIL',
        'seconds': 0.41,
        'violations': [
            {
                'path': 'src/a.py',
                'line': 3,
                'column': 1,
                'code': 'D103',
                'message': 'Missing docstring in public function',
            },
            {
                'path': 'src/b.py',
                'line': 1,
                'column': 1,
                'code': 'E501',
                'message': 'Line too long',
            },
        ],
        'raw': '[...]',
    }
    formatting: dict[str, object] = {
        'name': 'ruff-format',
        'status': 'PASS',
        'seconds': 0.08,
        'violations': [],
        'raw': '',
    }
    types: dict[str, object] = {
        'name': 'basedpyright',
        'status': 'ERROR',
        'seconds': 600,
        'violations': [],
        'raw': 'timeout after 600s',
    }
    assert document == {
        'mode': 'file',
        'base': None,
        'result': 'FAIL',
        'checks': [lint, formatting, types],
    }
