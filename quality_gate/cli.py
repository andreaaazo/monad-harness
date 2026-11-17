"""The command line of the gate (SPEC §7.1).

`python -m quality_gate MODE ...` runs one mode and prints its report:
`file PATH...` the per-file checks on the given Python files, `staged` the
commit hook's checks, `changed [--base REF]` the ratchet on what changed
since the base, `full` every check on the whole repository. The exit
code is 0 when every check passes, 1 when one fails or gives no verdict,
and 2 for a usage error, an internal error, or a folder outside a git
repository. `lock` writes a new lock after a person confirms it, and exits
0 when it was written and 2 otherwise. A SIGTERM stops the run, and the
tool it waits for, with 143 (128 + the signal), as a shell reports it.

The command line itself is read by `quality_gate.command`.
"""

import logging
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn, TextIO

from quality_gate.command import Command, parse_command
from quality_gate.execution import ToolError
from quality_gate.model import GateError, Report, Status
from quality_gate.modes.launch import run_lock, run_mode
from quality_gate.modes.session import open_session
from quality_gate.report import render_json, render_text

_USAGE_ERROR = 2
# A process ended by signal N exits 128 + N, as a shell reports it.
_SIGNALLED = 128


def exit_code(report: Report) -> int:
    """Turn a report into the gate's exit code.

    Args:
        report: The finished run.

    Returns:
        0 when every check passed, 1 otherwise.
    """
    return 0 if report.verdict is Status.PASS else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the gate from the command line.

    Args:
        argv: The arguments after the program; the process's when None.

    Returns:
        The exit code.
    """
    words = sys.argv[1:] if argv is None else argv
    # Each swap leaves in `spare` the handler that is not installed.
    spare = signal.signal(signal.SIGTERM, _terminated)
    try:
        return _dispatch(parse_command(words))
    except (GateError, ToolError) as error:
        _write(sys.stderr, f'quality-gate: {error}\n')
        return _USAGE_ERROR
    except Exception:
        logging.getLogger(__name__).exception('quality-gate: internal error')
        return _USAGE_ERROR
    finally:
        spare = signal.signal(signal.SIGTERM, spare or signal.SIG_DFL)


def _dispatch(command: Command) -> int:
    session = open_session(Path.cwd())
    if command.mode == 'lock':
        return run_lock(session)
    report = run_mode(command, session)
    if command.output == 'json':
        _write(sys.stdout, f'{render_json(report)}\n')
    else:
        _write(sys.stdout, render_text(report))
    return exit_code(report)


def _terminated(number: int, _frame: object) -> NoReturn:
    # SystemExit unwinds the run, so the tool it waits for is killed first.
    sys.exit(_SIGNALLED + number)


def _write(stream: TextIO, text: str) -> None:
    stream.writelines((text,))
