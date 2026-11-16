"""Tests of the ratchet's filter (SPEC §7.5)."""

from quality_gate.checks.scope import keep_in
from quality_gate.model import CheckResult, Status, Violation


def _found(path: str) -> Violation:
    return Violation(path=path, line=1, column=1, code='X1', message='m')


def _checked(status: Status, *paths: str) -> CheckResult:
    found = tuple(_found(path) for path in paths)
    return CheckResult('dead-code', status, 1, found, 'raw')


def test_keep_in_drops_findings_outside() -> None:
    """Findings outside the changed files go; with none left, it passes."""
    failing = _checked(Status.FAIL, 'a.py', 'b.py')
    kept = keep_in(failing, {'a.py'})
    assert (kept.status, kept.violations) == (Status.FAIL, (_found('a.py'),))
    assert keep_in(failing, {'c.py'}).status is Status.PASS


def test_keep_in_leaves_an_error_alone() -> None:
    """A check that gave no verdict stays an error whatever changed."""
    broken = _checked(Status.ERROR)
    assert keep_in(broken, {'a.py'}) == broken
