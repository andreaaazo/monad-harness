"""What Ruff's two checks share: how they run, and how its JSON reads."""

from pathlib import Path

from quality_gate.checks.verdict import ToolCheck, relative_path
from quality_gate.jsonvalue import is_array, is_table, load_json
from quality_gate.model import Violation


def ruff_check(name: str, command: tuple[str, ...]) -> ToolCheck:
    """Define one of Ruff's checks, which differ only in their command.

    Both read the root's configuration, keep no cache and print JSON.

    Args:
        name: The check's name, as SPEC §7.4 lists it.
        command: Ruff's subcommand and its own options.

    Returns:
        The check.
    """
    subcommand, *own = command
    return ToolCheck(
        name=name,
        tool='ruff',
        options=(
            subcommand,
            '--config',
            'pyproject.toml',
            '--no-cache',
            *own,
            '--output-format',
            'json',
        ),
        parse=parse_ruff_json,
        failing=frozenset((1,)),
    )


def parse_ruff_json(stdout: str, root: Path) -> tuple[Violation, ...]:
    """Read Ruff's `--output-format json` into violations.

    Args:
        stdout: Ruff's standard output: a JSON array of findings.
        root: The repository root, for the absolute file names.

    Returns:
        One violation per finding, in Ruff's order.

    Raises:
        ValueError: The output is not Ruff's array of findings.
    """
    document = load_json(stdout)
    if not is_array(document):
        message = 'Ruff did not print a JSON array'
        raise ValueError(message)
    return tuple(_violation(entry, root) for entry in document)


def _violation(entry: object, root: Path) -> Violation:
    fields: dict[str, object] = entry if is_table(entry) else {}
    where = fields.get('location')
    place: dict[str, object] = where if is_table(where) else {}
    return Violation(
        path=relative_path(root, _text(fields, 'filename')),
        line=_number(place, 'row'),
        column=_number(place, 'column'),
        code=_text(fields, 'code'),
        message=_text(fields, 'message'),
    )


def _text(fields: dict[str, object], key: str) -> str:
    match fields.get(key):
        case str(found):
            return found
        case _:
            message = f'Ruff printed a finding without a text {key}'
            raise ValueError(message)


def _number(place: dict[str, object], key: str) -> int:
    match place.get(key):
        case int(found):
            return found
        case _:
            message = f'Ruff printed a finding without a {key} number'
            raise ValueError(message)
