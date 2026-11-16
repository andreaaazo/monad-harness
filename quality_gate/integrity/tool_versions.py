"""The check `tool-versions`: every tool at exactly its pin (SPEC §8.5)."""

import re
import time
import tomllib
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path

from quality_gate.jsonvalue import is_array, is_table
from quality_gate.model import CheckResult, Status, Violation

_PIN = re.compile(
    r'(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[A-Za-z0-9.+!_-]+)',
)


def run(root: Path) -> CheckResult:
    """Compare the installed version of every quality tool with its pin.

    Args:
        root: The repository root, whose pyproject.toml holds the pins.

    Returns:
        The check's result, named `tool-versions`.
    """
    started = time.perf_counter()
    found = tuple(_problems(root))
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('tool-versions', status, seconds, found, '')


def _problems(root: Path) -> Iterator[Violation]:
    requirements = _quality_group(root / 'pyproject.toml')
    if requirements is None:
        message = 'pyproject.toml has no [dependency-groups] quality list'
        yield _violation('no-quality-group', message)
        return
    for requirement in requirements:
        problem = _problem(requirement)
        if problem is not None:
            yield problem


def _quality_group(path: Path) -> list[object] | None:
    try:
        document: object = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    groups = document.get('dependency-groups') if is_table(document) else None
    quality = groups.get('quality') if is_table(groups) else None
    return quality if is_array(quality) else None


def _problem(requirement: object) -> Violation | None:
    pin = _PIN.fullmatch(requirement) if isinstance(requirement, str) else None
    if pin is None:
        return _violation(
            'pin-not-exact', f'{requirement} is not pinned with =='
        )
    name, pinned = pin['name'], pin['version']
    try:
        installed = metadata.version(name)
    except metadata.PackageNotFoundError:
        return _violation('not-installed', f'{name} is not installed')
    if installed != pinned:
        message = f'{name} is {installed}, pinned {pinned}'
        return _violation('version-differs', message)
    return None


def _violation(code: str, message: str) -> Violation:
    return Violation('pyproject.toml', 1, 1, code, message)
