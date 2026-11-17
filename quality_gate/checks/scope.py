"""The ratchet's filter: only what touches a changed file counts (§7.5)."""

import dataclasses
from collections.abc import Callable, Collection, Iterable

from quality_gate.model import CheckResult, Status, Violation


def own_path(found: Violation) -> tuple[str]:
    """Name the one file a violation sits in.

    Args:
        found: A violation.

    Returns:
        Its path.
    """
    return (found.path,)


def keep_in(
    checked: CheckResult,
    paths: Collection[str],
    *,
    places: Callable[[Violation], Iterable[str]] = own_path,
) -> CheckResult:
    """Keep only the violations that touch the given files.

    The project checks run on the whole repository; in `changed`, only their
    findings that touch a changed file count.

    Args:
        checked: A check's result over the whole repository.
        paths: The changed files, root-relative.
        places: The files a violation touches; by default, its own path.

    Returns:
        The result with the other violations dropped: a failure with nothing
        left passes. An error stays an error, and a failure the gate could
        read no finding from stays a failure (§7.3).
    """
    if checked.status is Status.ERROR or not checked.violations:
        return checked
    kept = tuple(
        found
        for found in checked.violations
        if any(place in paths for place in places(found))
    )
    status = Status.FAIL if kept else Status.PASS
    return dataclasses.replace(checked, status=status, violations=kept)
