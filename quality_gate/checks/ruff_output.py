"""Ruff's JSON output, shared by its lint and format checks."""

from pathlib import Path

from quality_gate.checks.verdict import relative_path
from quality_gate.jsonvalue import is_array, is_table, load_json
from quality_gate.model import Violation


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
