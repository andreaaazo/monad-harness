"""The check `suppressions`: no directive that silences a tool (SPEC §8.1).

The scan reads the raw text of every given file, strings included: some tools
honour a directive wherever it stands. Case does not matter, and there is no
list of exceptions. A file that is not UTF-8 cannot be read, so it fails.

Each pattern below is written so that this file does not match it: a pattern
the scan found in its own source would have to be excused, and none is.
"""

import re
import time
from collections.abc import Iterable
from typing import Final

from quality_gate.checks.verdict import CheckInput
from quality_gate.model import CheckResult, Status, Violation

_PATTERNS: Final = (
    ('SUP001', r'\bnoqa\b', 'Ruff, flake8, vulture, pydoclint'),
    ('SUP002', r'type:\s*ignore', 'the type checker'),
    ('SUP003', r'pyright[:]', 'basedpyright'),
    ('SUP004', r'pragma:\s*no\s*(cover|branch|mutate)', 'coverage, mutmut'),
    ('SUP005', r'pylint:\s*\w', 'pylint'),
    ('SUP006', r'fmt:\s*(off|on|skip)', 'ruff format'),
    ('SUP007', r'isort:\s*\w', "Ruff's import sorting"),
    ('SUP008', r'pytest\.mark\.(skip|skipif|xfail)', 'pytest'),
    (
        'SUP009',
        r'(pytest|unittest)\.(skip|xfail|importorskip|SkipTest)',
        'pytest',
    ),
    (
        'SUP010',
        r"""
        collect[_]ignore | pytest[_]collection[_]modifyitems
        | pytest[_]ignore[_]collect | pytest[_]plugins
        """,
        'pytest',
    ),
)
# Verbose, so a long pattern can span lines: none holds a literal space.
_RULES: Final = tuple(
    (code, re.compile(pattern, re.IGNORECASE | re.VERBOSE), honoured_by)
    for code, pattern, honoured_by in _PATTERNS
)


def scan_text(path: str, text: str) -> tuple[Violation, ...]:
    """Find every directive in a file's text.

    Args:
        path: The file, root-relative, for the violations.
        text: The file's whole text.

    Returns:
        One violation per directive, at the line and column it starts.
    """
    return tuple(
        _violation(path, text, found=found, rule=(code, honoured_by))
        for code, pattern, honoured_by in _RULES
        for found in pattern.finditer(text)
    )


def run(given: CheckInput) -> CheckResult:
    """Scan the given files for directives.

    Args:
        given: The runner, whose root the files are below, and the files.

    Returns:
        The check's result, named `suppressions`.
    """
    started = time.perf_counter()
    found = tuple(_scan_files(given))
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('suppressions', status, seconds, found, '')


def _scan_files(given: CheckInput) -> Iterable[Violation]:
    for name in given.files:
        try:
            text = (given.runner.root / name).read_bytes().decode('utf-8')
        except UnicodeDecodeError:
            yield Violation(name, 1, 1, 'SUP000', 'the file is not UTF-8')
            continue
        yield from scan_text(name, text)


def _violation(
    path: str,
    text: str,
    *,
    found: re.Match[str],
    rule: tuple[str, str],
) -> Violation:
    code, honoured_by = rule
    start = found.start()
    shown = ' '.join(found.group().split())
    return Violation(
        path=path,
        line=text.count('\n', 0, start) + 1,
        column=start - text.rfind('\n', 0, start),
        code=code,
        message=f"'{shown}' silences {honoured_by}",
    )
