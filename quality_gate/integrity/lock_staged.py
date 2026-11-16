"""The check `lock-staged`: no new lock in a commit without approval (§8.3).

A lock changes only when Andrea locks a new configuration, and he commits it
with `QUALITY_GATE_LOCK_CHANGE_OK=1 git commit`. The variable is read from
the gate's own environment, which the commit hook inherits.
"""

import time
from collections.abc import Mapping

from quality_gate.changes import staged_paths
from quality_gate.execution import Runner
from quality_gate.integrity.lockfile import LOCK_PATH
from quality_gate.model import CheckResult, Status, Violation

_APPROVAL = 'QUALITY_GATE_LOCK_CHANGE_OK'
_UNAPPROVED = Violation(
    path=LOCK_PATH,
    line=1,
    column=1,
    code='lock-unapproved',
    message=f'commit a new lock with {_APPROVAL}=1 git commit',
)


def run(runner: Runner, environment: Mapping[str, str]) -> CheckResult:
    """Fail when the lock is staged without the approval variable.

    Args:
        runner: A runner rooted in the repository.
        environment: The gate's own environment.

    Returns:
        The check's result, named `lock-staged`.
    """
    started = time.perf_counter()
    staged = LOCK_PATH in staged_paths(runner)
    found = (
        (_UNAPPROVED,) if staged and environment.get(_APPROVAL) != '1' else ()
    )
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('lock-staged', status, seconds, found, '')
