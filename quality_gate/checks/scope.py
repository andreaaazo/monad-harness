"""The ratchet's filter: only what touches a changed file counts (§7.5)."""

import dataclasses
from collections.abc import Collection

from quality_gate.model import CheckResult, Status


def keep_in(checked: CheckResult, paths: Collection[str]) -> CheckResult:
    """Keep only the violations found in the given files.

    The project checks run on the whole repository; in `changed`, only their
    findings inside a changed file count.

    Args:
        checked: A check's result over the whole repository.
        paths: The changed files, root-relative.

    Returns:
        The result with the other violations dropped: a failure with nothing
        left passes, and an error stays an error.
    """
    if checked.status is Status.ERROR:
        return checked
    kept = tuple(found for found in checked.violations if found.path in paths)
    status = Status.FAIL if kept else Status.PASS
    return dataclasses.replace(checked, status=status, violations=kept)
