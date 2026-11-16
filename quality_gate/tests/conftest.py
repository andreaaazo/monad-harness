"""Fixtures shared by the gate's tests."""

from pathlib import Path

import pytest


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
