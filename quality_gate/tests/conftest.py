"""Fixtures shared by the gate's tests."""

from pathlib import Path

import pytest

from quality_gate.execution import Runner, runner_for


@pytest.fixture
def scripts(tmp_path: Path) -> Path:
    """Give a test an empty folder that plays the interpreter's scripts.

    Args:
        tmp_path: The test's own folder.

    Returns:
        The empty scripts folder.
    """
    folder = tmp_path / 'scripts'
    folder.mkdir()
    return folder


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Runner:
    """Give a test an empty git repository and a runner rooted in it.

    Inside a commit hook git exports GIT_INDEX_FILE, and `Runner.git` passes
    it on: the fixture drops it, so the repository's commands never write
    into another repository's index.

    Args:
        tmp_path: The test's own folder.
        monkeypatch: Removes the index variable for the test.

    Returns:
        A runner whose root is a fresh repository with no commit.
    """
    monkeypatch.delenv('GIT_INDEX_FILE', raising=False)
    root = tmp_path / 'repository'
    root.mkdir()
    runner = runner_for(root, (), 30)
    for arguments in (
        ('init', '-q'),
        ('config', 'user.name', 'Quality Gate Test'),
        ('config', 'user.email', 'quality-gate@example.invalid'),
    ):
        assert runner.git(arguments).exit_code == 0
    return runner


def commit_all(runner: Runner) -> None:
    """Commit every file of a temporary repository, as one snapshot.

    Tests commit only in repositories they made themselves (plan B, B2).

    Args:
        runner: A runner rooted in a temporary repository.
    """
    for arguments in (
        ('add', '-A'),
        ('-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'snapshot'),
    ):
        assert runner.git(arguments).exit_code == 0
