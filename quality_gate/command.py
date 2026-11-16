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
    '       python -m quality_gate changed [--base REF] [--format text|json]\n'
    '       python -m quality_gate lock'
)
_TEXT = 'text'
_FORMAT = '--format'
_BASE = '--base'
_FORMATS = frozenset((_TEXT, 'json'))
_PATHLESS = frozenset(('staged', 'full', 'changed'))
_OPTIONS = frozenset((_FORMAT, _BASE))
_LOCK = 'lock'
_HEAD = 'HEAD'


@dataclass(frozen=True, slots=True)
class Command:
    """One parsed command line.

    Attributes:
        mode: The mode to run.
        paths: The paths the user gave, which only `file` takes.
        output: The report's format: `text` or `json`.
        base: The reference `changed` compares with; the others ignore it.
    """

    mode: str
    paths: tuple[str, ...]
    output: str
    base: str = _HEAD


def parse_command(words: Sequence[str]) -> Command:
    """Read the arguments after `python -m quality_gate`.

    `file` takes one path or more, the other modes none. Every mode but
    `lock` takes `--format`, `changed` also `--base`, and `lock` takes
    nothing at all.

    Args:
        words: The command line, without the program.

    Returns:
        The mode, the paths, the output format and the base.

    Raises:
        GateError: The command is not one the gate knows.
    """
    mode = words[0] if words else ''
    if mode == _LOCK and len(words) == 1:
        return Command(mode=mode, paths=(), output=_TEXT)
    options, paths = _split_options(words[1:])
    if not _accepted(mode, options, paths):
        raise GateError(USAGE)
    return Command(
        mode=mode,
        paths=paths,
        output=options.get(_FORMAT, _TEXT),
        base=options.get(_BASE, _HEAD),
    )


def _accepted(
    mode: str,
    options: dict[str, str],
    paths: tuple[str, ...],
) -> bool:
    takes_paths = mode == 'file'
    known = takes_paths or mode in _PATHLESS
    return known and bool(paths) == takes_paths and _options_fit(mode, options)


def _options_fit(mode: str, options: dict[str, str]) -> bool:
    if _BASE in options and (mode != 'changed' or not options[_BASE]):
        return False
    return options.get(_FORMAT, _TEXT) in _FORMATS


def _split_options(
    words: Sequence[str],
) -> tuple[dict[str, str], tuple[str, ...]]:
    remaining = iter(words)
    options: dict[str, str] = {}
    paths: list[str] = []
    for word in remaining:
        if word in _OPTIONS:
            options[word] = next(remaining, '')
        elif word.startswith('--'):
            raise GateError(USAGE)
        else:
            paths.append(word)
    return options, tuple(paths)
