"""The `lock` mode: only a person at a terminal writes the lock (§8.3).

The mode refuses without an interactive terminal, inside Claude Code (which
sets `CLAUDECODE` in its commands), and while any integrity guard fails. It
then shows what changed since the last lock and writes the new one only if
the person types `LOCK`. A refusal is a usage error: exit 2.
"""

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

from quality_gate.integrity.lockfile import (
    LOCK_PATH,
    compute_lock,
    differences,
    render_lock,
)
from quality_gate.jsonvalue import is_table, load_json
from quality_gate.model import CheckResult, GateError, Status

type Guards = Callable[[], tuple[CheckResult, ...]]

_CONFIRMATION: Final = 'LOCK'
_ABORTED: Final = 2


@dataclass(frozen=True, slots=True)
class ConsoleTerminal:
    """The real terminal: the process's standard input and output.

    Attributes:
        stdin: Where the answer is read.
        stdout: Where the lines and the question are written.
    """

    stdin: TextIO
    stdout: TextIO

    def interactive(self) -> bool:
        """Tell whether both streams are terminals.

        Returns:
            True when a person can read and answer.
        """
        return self.stdin.isatty() and self.stdout.isatty()

    def show(self, text: str) -> None:
        """Write one line.

        Args:
            text: The line.
        """
        self.stdout.writelines((text, '\n'))

    def ask(self, prompt: str) -> str:
        """Write the question and read one line of answer.

        Args:
            prompt: The question.

        Returns:
            The answer, without its line end.
        """
        self.stdout.writelines((prompt,))
        self.stdout.flush()
        return self.stdin.readline().rstrip('\r\n')


def lock(
    root: Path,
    gate_files: Sequence[str],
    terminal: ConsoleTerminal,
    *,
    guards: Guards,
) -> int:
    """Write a new lock, if a person at a terminal confirms it.

    Args:
        root: The repository root.
        gate_files: The discovered files under `quality_gate/`.
        terminal: Where the person reads and answers.
        guards: The integrity checks that must pass first.

    Returns:
        0 when the lock was written, 2 when the person did not confirm.
    """
    _allowed(terminal, guards)
    current = compute_lock(root, gate_files)
    for line in differences(_previous(root / LOCK_PATH), current) or (
        'no change',
    ):
        terminal.show(line)
    if (
        terminal.ask(f'Type {_CONFIRMATION} to write the new lock: ')
        != _CONFIRMATION
    ):
        terminal.show('nothing written')
        return _ABORTED
    with (root / LOCK_PATH).open('w', encoding='utf-8') as written:
        written.writelines((render_lock(current),))
    return 0


def _allowed(terminal: ConsoleTerminal, guards: Guards) -> None:
    if not terminal.interactive():
        message = 'lock needs a terminal'
        raise GateError(message)
    if 'CLAUDECODE' in os.environ:
        message = 'lock cannot run inside Claude Code'
        raise GateError(message)
    failing = [found for found in guards() if found.status is not Status.PASS]
    if failing:
        lines = (line for check in failing for line in _described(check))
        message = '\n'.join(('lock needs every guard to pass:', *lines))
        raise GateError(message)


def _described(check: CheckResult) -> tuple[str, ...]:
    status = check.status.name
    found = (violation.render() for violation in check.violations)
    return (f'{check.name} {status}', *found)


def _previous(path: Path) -> dict[str, object] | None:
    try:
        stored = load_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return stored if is_table(stored) else None
