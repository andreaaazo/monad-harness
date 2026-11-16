"""The command line of the gate (SPEC §7.1).

`python -m quality_gate file PATH... [--format text|json]` runs the per-file
checks on the given paths that are discovered Python files. The exit code is
0 when every check passes, 1 when one fails or gives no verdict, and 2 for a
usage error, an internal error, or a folder outside a git repository.

The command line itself is read by `quality_gate.command`.
"""

import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from quality_gate.command import Command, parse_command
from quality_gate.discovery import find_root
from quality_gate.execution import ToolError, runner_for
from quality_gate.model import GateError, Report, Status
from quality_gate.modes import run_file_mode
from quality_gate.report import render_json, render_text
from quality_gate.settings import load_settings

_PROBE_SECONDS = 60
_USAGE_ERROR = 2


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
    try:
        command, report = _run(words)
    except (GateError, ToolError) as error:
        _write(sys.stderr, f'quality-gate: {error}\n')
        return _USAGE_ERROR
    except Exception:
        logging.getLogger(__name__).exception('quality-gate: internal error')
        return _USAGE_ERROR
    if command.output == 'json':
        _write(sys.stdout, f'{render_json(report)}\n')
    else:
        _write(sys.stdout, render_text(report))
    return exit_code(report)


def _run(words: Sequence[str]) -> tuple[Command, Report]:
    command = parse_command(words)
    root = find_root(runner_for(Path.cwd(), (), _PROBE_SECONDS))
    settings = load_settings(root)
    runner = runner_for(
        root,
        settings.env_passthrough,
        settings.check_timeout_seconds,
    )
    return command, run_file_mode(runner, settings, command.paths)


def _write(stream: TextIO, text: str) -> None:
    stream.writelines((text,))
