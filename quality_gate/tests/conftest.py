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
def repository(tmp_path: Path) -> Runner:
    """Give a test an empty git repository and a runner rooted in it.

    Args:
        tmp_path: The test's own folder.

    Returns:
        A runner whose root is a fresh repository with no commit.
    """
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
