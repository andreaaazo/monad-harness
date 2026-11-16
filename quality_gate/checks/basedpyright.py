"""The check `basedpyright`: types, in mode `all` (SPEC §6.4).

The check passes only when basedpyright exits 0 and counts no error and no
warning. A count that names no diagnostic still fails.
"""

import sys
from pathlib import Path

from quality_gate.checks.verdict import (
    CheckInput,
    ToolCheck,
    relative_path,
    run_tool_check,
)
from quality_gate.jsonvalue import is_array, is_table, load_json
from quality_gate.model import CheckResult, Violation

_COUNTED = frozenset(('error', 'warning'))


def parse_basedpyright(stdout: str, root: Path) -> tuple[Violation, ...]:
    """Read basedpyright's `--outputjson` report into violations.

    Output that is not basedpyright's report raises ValueError.

    Args:
        stdout: The JSON report, with its diagnostics and summary.
        root: The repository root, for the absolute file names.

    Returns:
        One violation per error or warning, counted from 1; or, when the
        summary counts findings it did not list, one `summary` violation.
    """
    summary, diagnostics = _sections(load_json(stdout))
    found = tuple(
        _violation(entry, root)
        for entry in diagnostics
        if _severity(entry) in _COUNTED
    )
    counted = _count(summary, 'errorCount') + _count(summary, 'warningCount')
    if found or not counted:
        return found
    message = f'basedpyright counted {counted} findings it did not list'
    return (Violation('.', 1, 1, 'summary', message),)


def _sections(document: object) -> tuple[dict[str, object], list[object]]:
    report: dict[str, object] = document if is_table(document) else {}
    summary = report.get('summary')
    diagnostics = report.get('generalDiagnostics')
    if is_table(summary) and is_array(diagnostics):
        return summary, diagnostics
    message = 'basedpyright printed no report the gate can read'
    raise ValueError(message)


def _severity(entry: object) -> str:
    match entry:
        case {'severity': str(severity)}:
            return severity
        case _:
            message = (
                f'basedpyright printed a diagnostic without severity: {entry}'
            )
            raise ValueError(message)


def _violation(entry: object, root: Path) -> Violation:
    match entry:
        case {
            'file': str(path),
            'message': str(message),
            'range': {'start': {'line': int(line), 'character': int(column)}},
        }:
            return Violation(
                path=relative_path(root, path),
                line=line + 1,
                column=column + 1,
                code=_rule(entry),
                message=message,
            )
        case _:
            message = (
                f'basedpyright printed a diagnostic without place: {entry}'
            )
            raise ValueError(message)


def _rule(entry: object) -> str:
    match entry:
        case {'rule': str(rule)}:
            return rule
        case _:
            return 'basedpyright'


def _count(summary: dict[str, object], key: str) -> int:
    match summary.get(key):
        case int(count):
            return count
        case _:
            message = f'basedpyright printed a summary without {key}'
            raise ValueError(message)


CHECK = ToolCheck(
    name='basedpyright',
    tool='basedpyright',
    options=(
        '--project',
        'pyproject.toml',
        '--pythonpath',
        sys.executable,
        '--outputjson',
    ),
    parse=parse_basedpyright,
    failing=frozenset((1,)),
)


def run(given: CheckInput) -> CheckResult:
    """Check the types of the given files.

    Args:
        given: The runner and the files.

    Returns:
        The check's result.
    """
    return run_tool_check(CHECK, given)
