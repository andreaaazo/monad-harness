"""The check `hook-integrity`: the hooks are there, and on (SPEC §8.4).

The check reads Claude Code's project settings, its local and user settings,
and git's commit hook. It also fails when `core.hooksPath` is set, since git
would then never run `.git/hooks/pre-commit` (plan B, B7).
"""

import time
from collections.abc import Iterator, Mapping
from functools import partial
from pathlib import Path
from typing import Final

from quality_gate.execution import Runner
from quality_gate.jsonvalue import is_table, load_json
from quality_gate.model import CheckResult, Status, Violation

# Twice <T_SUITE> (107 s, plan A), plus 120: what §9.1 asks of the Stop hook.
STOP_TIMEOUT: Final = 334
# The line pre-commit 4.7.0 writes in every hook it installs.
PRE_COMMIT_MARKER: Final = '# ID: 138fd403232d2ddd5efb44317e38bf03'
_SETTINGS: Final = '.claude/settings.json'
_LOCAL: Final = '.claude/settings.local.json'
_HOOK: Final = '.git/hooks/pre-commit'
_HOOKS: Final = 'hooks'
_FAST: Final = 10
_POST_EDIT: Final = 120
# Variables the gate reads besides its own QUALITY_GATE_*: CI skips the
# commit hook, CLAUDECODE marks an agent.
_GATE_VARIABLES: Final = frozenset(('CI', 'CLAUDECODE'))
_problem: Final = partial(Violation, line=1, column=1, code=_HOOKS)


def expected_hooks() -> dict[str, object]:
    """Build the `hooks` object of §9.1, as `.claude/settings.json` holds it.

    Returns:
        The four registrations, with the interpreter `.venv/bin/python`.
    """
    return {
        'PreToolUse': [_registration('guard', _FAST, matcher='*')],
        'PostToolUse': [
            _registration(
                'post-edit',
                _POST_EDIT,
                matcher='Write|Edit|MultiEdit|NotebookEdit',
            ),
        ],
        'Stop': [_registration('stop', STOP_TIMEOUT, matcher=None)],
        'ConfigChange': [
            _registration(
                'config-change',
                _FAST,
                matcher='project_settings|local_settings',
            ),
        ],
    }


def run(
    root: Path,
    home: Path,
    runner: Runner,
    *,
    environment: Mapping[str, str],
) -> CheckResult:
    """Check every condition of §8.4.

    Args:
        root: The repository root.
        home: The user's home folder.
        runner: A runner rooted in the repository, for git's configuration.
        environment: The gate's own environment: `CI` skips the commit hook.

    Returns:
        The check's result, named `hook-integrity`.
    """
    started = time.perf_counter()
    found = (
        *_project(root / _SETTINGS),
        *_overrides(root / _LOCAL, _LOCAL, local=True),
        *_overrides(home / _SETTINGS, f'~/{_SETTINGS}', local=False),
        *(() if environment.get('CI') else _commit_hook(root, runner)),
    )
    status = Status.FAIL if found else Status.PASS
    seconds = time.perf_counter() - started
    return CheckResult('hook-integrity', status, seconds, found, '')


def _registration(
    name: str,
    timeout: int,
    *,
    matcher: str | None,
) -> dict[str, object]:
    command = (
        'cd "$CLAUDE_PROJECT_DIR" && .venv/bin/python -m quality_gate '
        f'hook {name} || exit 2'
    )
    hook = {'type': 'command', 'timeout': timeout, 'command': command}
    entry: dict[str, object] = {_HOOKS: [hook]}
    return entry if matcher is None else {'matcher': matcher, **entry}


def _project(path: Path) -> Iterator[Violation]:
    settings = _read(path)
    if settings is None:
        yield _problem(_SETTINGS, message='missing or not a JSON object')
    elif settings.get('disableAllHooks') is not False:
        yield _problem(_SETTINGS, message='disableAllHooks must be false')
    elif settings.get(_HOOKS) != expected_hooks():
        yield _problem(_SETTINGS, message="the hooks differ from the gate's")


def _overrides(path: Path, label: str, *, local: bool) -> Iterator[Violation]:
    if not path.exists():
        return
    settings = _read(path)
    if settings is None:
        yield _problem(label, message='not a JSON object')
        return
    if local and (
        settings.get('disableAllHooks') is True or _HOOKS in settings
    ):
        yield _problem(
            label, message='local settings cannot turn off or replace hooks'
        )
    variables = settings.get('env')
    names = list(variables) if is_table(variables) else []
    for name in names:
        if name.startswith('QUALITY_GATE_') or name in _GATE_VARIABLES:
            yield _problem(label, message=f'env cannot set {name}')


def _commit_hook(root: Path, runner: Runner) -> Iterator[Violation]:
    hook = root / _HOOK
    installed = hook.is_file() and PRE_COMMIT_MARKER in hook.read_text(
        encoding='utf-8',
        errors='replace',
    )
    if not installed:
        yield _problem(_HOOK, message='missing, or not installed by pre-commit')
    if runner.git(('config', '--get', 'core.hooksPath')).exit_code == 0:
        yield _problem('.git/config', message='core.hooksPath skips .git/hooks')


def _read(path: Path) -> dict[str, object] | None:
    try:
        settings = load_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return settings if is_table(settings) else None
