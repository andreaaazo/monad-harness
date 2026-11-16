"""The check `duplication`: no copied block of four lines, via pylint (§6.6).

pylint names the files of a duplicate block by module, and its own `path`
field names whichever file it read last. The gate maps each module back to
a discovered file the way pylint names modules: the dotted path from the
first folder without `__init__.py` (plan B, B9).
"""

import re
from collections.abc import Sequence
from functools import partial
from pathlib import Path, PurePosixPath

from quality_gate.checks.verdict import CheckInput, ToolCheck, run_tool_check
from quality_gate.jsonvalue import is_array, load_json
from quality_gate.model import CheckResult, Violation

_BLOCK = re.compile(r'==(?P<module>[\w.]+):\[(?P<start>\d+):(?P<end>\d+)\]')
_LISTED = re.compile(r'(?P<path>[^,\s]+):\d+-\d+')


def module_name(path: str, root: Path) -> str:
    """Name a file's module as pylint does.

    Args:
        path: The file, root-relative.
        root: The repository root.

    Returns:
        The dotted path from the first parent folder without `__init__.py`.
    """
    relative = PurePosixPath(path)
    names = [] if relative.stem == '__init__' else [relative.stem]
    folder = relative.parent
    while folder.name and (root / folder / '__init__.py').is_file():
        names.insert(0, folder.name)
        folder = folder.parent
    return '.'.join(names)


def parse_pylint(
    stdout: str,
    root: Path,
    *,
    files: Sequence[str],
) -> tuple[Violation, ...]:
    """Read pylint's JSON messages into one violation per duplicate block.

    Args:
        stdout: pylint's JSON list of messages.
        root: The repository root.
        files: The files pylint read, to name the blocks' modules.

    Returns:
        One violation per block, at its first file's first line.

    Raises:
        ValueError: The output is not pylint's list of duplicate blocks.
    """
    document = load_json(stdout)
    if not is_array(document):
        message = 'pylint printed no list of messages'
        raise ValueError(message)
    modules = {module_name(path, root): path for path in files}
    return tuple(_block(entry, modules) for entry in document)


def block_paths(found: Violation) -> tuple[str, ...]:
    """Read back every file a duplicate block touches.

    Args:
        found: A violation of this check.

    Returns:
        The files of the block, root-relative.
    """
    _, _, listed = found.message.partition(': ')
    return tuple(listing['path'] for listing in _LISTED.finditer(listed))


def run(given: CheckInput) -> CheckResult:
    """Look for duplicated code across every given file.

    Args:
        given: The runner and every discovered file.

    Returns:
        The check's result, named `duplication`.
    """
    check = ToolCheck(
        name='duplication',
        tool='pylint',
        options=(
            '--rcfile',
            'pyproject.toml',
            '--output-format',
            'json',
            '--persistent',
            'n',
        ),
        parse=partial(parse_pylint, files=given.files),
        failing=frozenset((8,)),
    )
    return run_tool_check(check, given)


def _block(entry: object, modules: dict[str, str]) -> Violation:
    match entry:
        case {'symbol': 'duplicate-code', 'message': str(message)}:
            places = _places(message, modules)
        case _:
            places = ()
    if not places:
        message = f'pylint printed a message the gate cannot read: {entry}'
        raise ValueError(message)
    listed = ', '.join(_place(place) for place in places)
    return Violation(
        places[0][0],
        places[0][1],
        1,
        'R0801',
        f'similar lines in {len(places)} files: {listed}',
    )


def _places(
    message: str,
    modules: dict[str, str],
) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (
            modules.get(found['module'], found['module']),
            int(found['start']) + 1,
            int(found['end']),
        )
        for found in _BLOCK.finditer(message)
    )


def _place(place: tuple[str, int, int]) -> str:
    path, start, end = place
    return f'{path}:{start}-{end}'
