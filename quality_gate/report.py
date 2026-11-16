"""The gate's report, as text and as JSON (SPEC §7.6).

Every check appears in the fixed order it ran, with its status, the number of
violations and its time. Below the table, each check that did not pass shows
its violations, one per line, or the tool's own output when it named none.
"""

import json

from quality_gate.model import CheckResult, Report, Status

# The table's columns: the name and the status align left, the numbers right.
_NAME_WIDTH = 18
_STATUS_WIDTH = 6
_COUNT_WIDTH = 7
_SECONDS_WIDTH = 9
_TABLE_HEADER = ''.join((
    'CHECK'.ljust(_NAME_WIDTH),
    'STATUS'.ljust(_STATUS_WIDTH),
    'COUNT'.rjust(_COUNT_WIDTH),
    'SECONDS'.rjust(_SECONDS_WIDTH),
))


def render_text(report: Report) -> str:
    """Write the report as text, as the terminal and the hooks show it.

    Args:
        report: The finished run.

    Returns:
        The text, ending with a newline.
    """
    lines = [
        _header(report),
        _TABLE_HEADER,
        *(_row(check) for check in report.checks),
        _summary(report),
    ]
    failing = [
        check for check in report.checks if check.status is not Status.PASS
    ]
    if failing:
        lines.append('')
    for check in failing:
        lines.extend(_details(check))
    return '\n'.join((*lines, ''))


def render_json(report: Report) -> str:
    """Write the report as JSON, for a program to read.

    Args:
        report: The finished run.

    Returns:
        A JSON object with `mode`, `base`, `result` and `checks`.
    """
    document = {
        'mode': report.mode,
        'base': report.base,
        'result': report.verdict.name,
        'checks': [_check_document(check) for check in report.checks],
    }
    return json.dumps(document, ensure_ascii=False, indent=2)


def _header(report: Report) -> str:
    parts = ['quality-gate', report.mode]
    if report.base is not None:
        parts.append(f' base={report.base}')
    parts.append(f' python-files={report.python_files}')
    return ' '.join(parts)


def _row(check: CheckResult) -> str:
    found = str(len(check.violations))
    count = '-' if check.status is Status.ERROR else found
    seconds = format(check.seconds, '.2f')
    return ''.join((
        check.name.ljust(_NAME_WIDTH),
        check.status.name.ljust(_STATUS_WIDTH),
        count.rjust(_COUNT_WIDTH),
        seconds.rjust(_SECONDS_WIDTH),
    ))


def _summary(report: Report) -> str:
    verdict = report.verdict.name
    return '  '.join((
        f'RESULT: {verdict}',
        f'failed={report.failed}',
        f'errors={report.errors}',
        f'checks={len(report.checks)}',
    ))


def _details(check: CheckResult) -> list[str]:
    if check.status is Status.ERROR:
        heading = f'== {check.name} (ERROR) =='
    else:
        heading = f'== {check.name} ({len(check.violations)}) =='
    if check.violations:
        return [
            heading,
            *(found.render() for found in sorted(check.violations)),
        ]
    return [heading, *check.raw.splitlines()]


def _check_document(check: CheckResult) -> dict[str, object]:
    return {
        'name': check.name,
        'status': check.status.name,
        'seconds': check.seconds,
        'violations': [
            {
                'path': found.path,
                'line': found.line,
                'column': found.column,
                'code': found.code,
                'message': found.message,
            }
            for found in sorted(check.violations)
        ],
        'raw': check.raw,
    }
