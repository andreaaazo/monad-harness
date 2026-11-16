"""Tests of the choice of mode, with every mode replaced by a stub."""

from functools import partial

import pytest

from quality_gate.command import Command
from quality_gate.execution import Runner
from quality_gate.integrity.guards import Host
from quality_gate.model import Report
from quality_gate.modes import launch
from quality_gate.modes.session import Session
from quality_gate.settings import Settings

FUNCTIONS = (
    ('file', 'run_file_mode'),
    ('staged', 'run_staged'),
    ('full', 'run_full'),
)


def _report(mode: str, *_arguments: object) -> Report:
    return Report(mode=mode, base=None, python_files=0, checks=())


@pytest.mark.parametrize('mode', ['file', 'staged', 'full'])
def test_each_mode_runs_its_own_function(
    mode: str,
    repository: Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each mode reaches its own function, and no other.

    Args:
        mode: The mode on the command line.
        repository: A fresh repository.
        monkeypatch: Replaces each mode's function by a stub naming it.
    """
    for name, function in FUNCTIONS:
        monkeypatch.setattr(launch, function, partial(_report, name))
    session = Session(
        runner=repository,
        settings=Settings(
            exclude=(),
            env_passthrough=(),
            check_timeout_seconds=30,
            mutation_min_score=0.9,
        ),
        host=Host(environment={}, home=repository.root.parent),
    )
    paths = ('a.py',) if mode == 'file' else ()
    command = Command(mode=mode, paths=paths, output='text')
    assert launch.run_mode(command, session).mode == mode
