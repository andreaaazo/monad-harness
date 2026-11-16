"""What a check finds, and what the gate reports (SPEC §7.6)."""

import enum
from dataclasses import dataclass


class Status(enum.Enum):
    """The outcome of one check. There is no "skipped" (SPEC §7.6).

    The report writes a status by its name.

    Attributes:
        PASS: The check found nothing.
        FAIL: The check found something, or its tool said so.
        ERROR: The check gave no verdict: a missing tool, a timeout, an
            exit code or an output nobody expects. It counts as a failure.
    """

    PASS = enum.auto()
    FAIL = enum.auto()
    ERROR = enum.auto()


class GateError(Exception):
    """A usage error or an internal error of the gate: exit code 2."""


@dataclass(frozen=True, slots=True, order=True)
class Violation:
    """One finding of a check, at a place in a file.

    Violations sort by path, then line and column as numbers.

    Attributes:
        path: The file, relative to the root, in POSIX form.
        line: The line, counted from 1.
        column: The column, counted from 1.
        code: The tool's code for the rule.
        message: The tool's explanation.
    """

    path: str
    line: int
    column: int
    code: str
    message: str

    def render(self) -> str:
        """Write the violation as one line of the text report.

        Returns:
            The line `path:line:column CODE message`.
        """
        place = f'{self.path}:{self.line}:{self.column}'
        return f'{place} {self.code} {self.message}'


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The outcome of one check.

    Attributes:
        name: The check's name, as SPEC §7.4 lists it.
        status: PASS, FAIL or ERROR.
        seconds: How long the check ran.
        violations: What it found.
        raw: The tool's own output, shown when it found nothing it can name.
    """

    name: str
    status: Status
    seconds: float
    violations: tuple[Violation, ...]
    raw: str


@dataclass(frozen=True, slots=True)
class Report:
    """Every check of one run of the gate.

    Attributes:
        mode: The mode the gate ran in.
        base: The commit `changed` compares with, or None.
        python_files: How many Python files the per-file checks saw.
        checks: The checks, in the order of SPEC §7.4.
    """

    mode: str
    base: str | None
    python_files: int
    checks: tuple[CheckResult, ...]

    @property
    def verdict(self) -> Status:
        """Tell whether the run passed.

        Returns:
            PASS when every check passed, FAIL otherwise.
        """
        statuses = {check.status for check in self.checks}
        return Status.PASS if statuses <= {Status.PASS} else Status.FAIL

    @property
    def failed(self) -> int:
        """Count the checks that failed.

        Returns:
            The number of checks in FAIL.
        """
        return self._count(Status.FAIL)

    @property
    def errors(self) -> int:
        """Count the checks that could not give a verdict.

        Returns:
            The number of checks in ERROR.
        """
        return self._count(Status.ERROR)

    def _count(self, status: Status) -> int:
        return sum(1 for check in self.checks if check.status is status)
