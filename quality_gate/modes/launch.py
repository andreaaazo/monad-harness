"""Run the mode a command names (SPEC §7.1, §7.5).

`file`, `staged`, `full` and `changed` each give a report. `lock` gives an
exit code: it writes the new lock only after its guards pass and a person at
the terminal types the confirmation.
"""

import sys
from functools import partial

from quality_gate.command import Command
from quality_gate.discovery import discover
from quality_gate.integrity.guards import gate_files, run_guards
from quality_gate.integrity.locking import ConsoleTerminal, lock
from quality_gate.model import Report
from quality_gate.modes.changed import run_changed
from quality_gate.modes.file import run_file_mode
from quality_gate.modes.session import Session
from quality_gate.modes.whole import run_full, run_staged


def run_mode(command: Command, session: Session) -> Report:
    """Run the checks of the command's mode.

    Args:
        command: A command whose mode is `file`, `staged`, `full` or
            `changed`.
        session: The repository, its settings and the host.

    Returns:
        The mode's report.
    """
    runner, settings, host = session.runner, session.settings, session.host
    match command.mode:
        case 'full':
            return run_full(runner, settings, host)
        case 'staged':
            return run_staged(runner, settings, host)
        case 'changed':
            return run_changed(runner, settings, host, base=command.base)
        case _:
            return run_file_mode(runner, settings, command.paths)


def run_lock(session: Session) -> int:
    """Write a new lock, through the terminal the gate was started from.

    Args:
        session: The repository, its settings and the host.

    Returns:
        0 when the lock was written, 2 when the person did not confirm.
    """
    discovered = discover(session.runner, session.settings.exclude)
    return lock(
        session.runner.root,
        gate_files(discovered),
        ConsoleTerminal(sys.stdin, sys.stdout),
        guards=partial(run_guards, session.runner, session.host),
    )
