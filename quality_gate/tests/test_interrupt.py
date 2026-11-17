"""Tests of the gate stopped by a signal: its tools stop with it."""

import os
import signal
import threading
import time
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

from quality_gate import cli
from quality_gate.execution import Runner
from quality_gate.model import Report
from quality_gate.tests.fakes import with_fakes, write_file, write_tool

CONFIG = (
    '[tool.quality_gate]\n'
    'exclude = []\n'
    'env_passthrough = []\n'
    'check_timeout_seconds = 120\n'
    'mutation_min_score = 0.9\n'
)
# Says it started, then works for two seconds, then says it finished.
SLOW = (
    'import pathlib, sys, time\n'
    'pathlib.Path(sys.argv[1]).touch()\n'
    'time.sleep(2)\n'
    'pathlib.Path(sys.argv[2]).touch()\n'
)


def _slow_mode(runner: Runner, marks: tuple[str, str], *_: object) -> Report:
    # One statement: the signal ends it inside the tool's run.
    return Report(
        mode='file',
        base=None,
        python_files=runner.tool('slow', marks).exit_code,
        checks=(),
    )


def _signal_once_started(started: Path, number: int) -> None:
    deadline = time.monotonic() + 10
    while not started.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    os.kill(os.getpid(), number)


@pytest.fixture
def sigterm_ignored() -> Iterator[None]:
    """Ignore SIGTERM during a test, then put the old handler back.

    Yields:
        Nothing: the test runs with SIGTERM ignored.
    """
    # Each swap leaves in `spare` the handler that is not installed.
    spare = signal.signal(signal.SIGTERM, signal.SIG_IGN)
    yield
    spare = signal.signal(signal.SIGTERM, spare or signal.SIG_DFL)


@pytest.mark.usefixtures('sigterm_ignored')
def test_sigterm_stops_the_gate_and_its_tool(
    repository: Runner,
    scripts: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIGTERM ends the run with 143, kills the tool, and restores the handler.

    The test ignores SIGTERM meanwhile: if the gate did not catch it, the
    run would finish instead of ending, and the test would fail.

    Args:
        repository: A fresh repository, where the gate runs.
        scripts: A scripts folder with a slow tool.
        monkeypatch: Moves into the repository and slows the file mode.
    """
    started, finished = scripts.parent / 'started', scripts.parent / 'finished'
    write_tool(scripts, 'slow', SLOW)
    write_file(repository.root, 'pyproject.toml', CONFIG)
    monkeypatch.chdir(repository.root)
    marks = (str(started), str(finished))
    slow = partial(_slow_mode, with_fakes(repository, scripts), marks)
    monkeypatch.setattr('quality_gate.modes.launch.run_file_mode', slow)
    threading.Thread(
        target=_signal_once_started,
        args=(started, signal.SIGTERM),
        daemon=True,
    ).start()
    with pytest.raises(SystemExit, match=r'^143$'):
        pytest.fail(repr(cli.main(['file', 'a.py'])))
    assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
    time.sleep(3)
    assert started.exists()
    assert not finished.exists()
