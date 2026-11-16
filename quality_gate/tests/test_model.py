"""Tests of the result model: violations, check results and the report."""

from quality_gate.model import CheckResult, Report, Status, Violation


def _check(name: str, status: Status) -> CheckResult:
    return CheckResult(
        name=name,
        status=status,
        seconds=0,
        violations=(),
        raw='',
    )


def _report(*statuses: Status) -> Report:
    return Report(
        mode='file',
        base=None,
        python_files=1,
        checks=tuple(
            _check(f'check-{index}', status)
            for index, status in enumerate(statuses)
        ),
    )


def test_violation_renders_as_one_line() -> None:
    """A violation is one line: path, line, column, code and message."""
    violation = Violation(
        path='src/a.py',
        line=10,
        column=5,
        code='D103',
        message='Missing docstring in public function',
    )
    assert violation.render() == (
        'src/a.py:10:5 D103 Missing docstring in public function'
    )


def test_report_passes_only_if_all_pass() -> None:
    """One check that does not pass fails the report; both kinds count."""
    assert _report(Status.PASS, Status.PASS).verdict is Status.PASS
    assert _report(Status.PASS, Status.ERROR).verdict is Status.FAIL
    mixed = _report(Status.FAIL, Status.PASS, Status.ERROR, Status.FAIL)
    assert (mixed.failed, mixed.errors) == (2, 1)
