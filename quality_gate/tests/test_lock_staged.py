"""Tests of `lock-staged`: no new lock in a commit without approval."""

from quality_gate.execution import Runner
from quality_gate.integrity import lock_staged
from quality_gate.integrity.lockfile import LOCK_PATH
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file

APPROVAL = 'QUALITY_GATE_LOCK_CHANGE_OK'


def _with_lock(repository: Runner, *, staged: bool) -> Runner:
    write_file(repository.root, LOCK_PATH, '{}\n')
    if staged:
        assert repository.git(('add', LOCK_PATH)).exit_code == 0
    return repository


def test_a_staged_lock_needs_approval(repository: Runner) -> None:
    """A lock in the index without the approval variable fails.

    Args:
        repository: A fresh repository.
    """
    runner = _with_lock(repository, staged=True)
    outcome = lock_staged.run(runner, {})
    assert (outcome.name, outcome.status) == ('lock-staged', Status.FAIL)
    assert [found.code for found in outcome.violations] == ['lock-unapproved']


def test_an_approved_lock_passes(repository: Runner) -> None:
    """With the approval variable set to 1 the lock may be committed.

    Args:
        repository: A fresh repository.
    """
    runner = _with_lock(repository, staged=True)
    assert lock_staged.run(runner, {APPROVAL: '1'}).status is Status.PASS
    assert lock_staged.run(runner, {APPROVAL: 'yes'}).status is Status.FAIL


def test_an_unstaged_lock_passes(repository: Runner) -> None:
    """A lock on disk but not in the index is no commit's business.

    Args:
        repository: A fresh repository.
    """
    runner = _with_lock(repository, staged=False)
    assert lock_staged.run(runner, {}).status is Status.PASS
