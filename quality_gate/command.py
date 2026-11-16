"""The gate's command line, parsed by hand (SPEC §7.1).

argparse does not fit the gate's rules: its `add_argument` returns an action
that basedpyright wants used, and its namespace holds values of type `Any`.
The grammar is small enough to read directly.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from quality_gate.model import GateError

USAGE = (
    'usage: python -m quality_gate file PATH... [--format text|json]\n'
    '       python -m quality_gate staged|full [--format text|json]\n'
    '       python -m quality_gate lock'
)
_FORMATS = frozenset(('text', 'json'))
_PATHLESS = frozenset(('staged', 'full'))
_LOCK = 'lock'


@dataclass(frozen=True, slots=True)
class Command:
    """One parsed command line.

    Attributes:
        mode: The mode to run.
        paths: The paths the user gave, which only `file` takes.
        output: The report's format: `text` or `json`.
    """

    mode: str
    paths: tuple[str, ...]
    output: str


def parse_command(words: Sequence[str]) -> Command:
    """Read the arguments after `python -m quality_gate`.

    `file` takes one path or more, `staged` and `full` none, and every mode
    but `lock` takes `--format`. `lock` takes nothing at all.

    Args:
        words: The command line, without the program.

    Returns:
        The mode, the paths and the output format.

    Raises:
        GateError: The command is not one the gate knows.
    """
    mode = words[0] if words else ''
    if mode == _LOCK and len(words) == 1:
        return Command(mode=mode, paths=(), output='text')
    output, paths = _split_format(words[1:])
    takes_paths = mode == 'file'
    known = takes_paths or mode in _PATHLESS
    if not known or bool(paths) != takes_paths or output not in _FORMATS:
        raise GateError(USAGE)
    return Command(mode=mode, paths=paths, output=output)


def _split_format(words: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    remaining = iter(words)
    output = 'text'
    paths: list[str] = []
    for word in remaining:
        if word == '--format':
            output = next(remaining, '')
        elif word.startswith('--'):
            raise GateError(USAGE)
        else:
            paths.append(word)
    return output, tuple(paths)
