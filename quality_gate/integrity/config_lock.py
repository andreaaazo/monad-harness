"""The check `config-lock`: the gate's configuration as it was locked (§8.3).

The lock does not stop a change. It makes every change to the gate one
visible difference in one file, which no commit takes without Andrea's
approval (`lock-staged`). The document itself is `lockfile`'s.
"""

import time
from collections.abc import Sequence
from pathlib import Path

from quality_gate.integrity.lockfile import LOCK_PATH, compute_lock, differences
from quality_gate.jsonvalue import is_table, load_json
from quality_gate.model import CheckResult, Status, Violation


def run(root: Path, gate_files: Sequence[str]) -> CheckResult:
    """Compare the stored lock with the configuration as it is now.

    Args:
        root: The repository root.
        gate_files: The discovered files under `quality_gate/`.

    Returns:
        The check's result, named `config-lock`.
    """
    started = time.perf_counter()
    try:
        stored = _stored(root / LOCK_PATH)
    except ValueError as error:
        found = (Violation(LOCK_PATH, 1, 1, 'lock-unreadable', str(error)),)
    else:
        found = tuple(
            Violation(LOCK_PATH, 1, 1, 'lock-differs', line)
            for line in differences(stored, compute_lock(root, gate_files))
        )
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('config-lock', status, seconds, found, '')


def _stored(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    stored = load_json(path.read_text(encoding='utf-8'))
    if not is_table(stored):
        message = 'the lock is not a JSON object'
        raise ValueError(message)
    return stored
