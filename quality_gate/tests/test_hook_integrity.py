"""Tests of `hook-integrity`: the hooks are there and nobody turned them off."""

import json
from pathlib import Path

import pytest

from quality_gate.execution import Runner
from quality_gate.integrity import hook_integrity
from quality_gate.model import Status
from quality_gate.tests.fakes import write_file

SETTINGS = '.claude/settings.json'
LOCAL = '.claude/settings.local.json'
HOOK = '.git/hooks/pre-commit'


def _json(document: object) -> str:
    return f'{json.dumps(document, indent=2)}\n'


@pytest.fixture
def home(repository: Runner) -> Path:
    """Put the gate's hooks in place, and give a fresh home folder.

    Args:
        repository: A fresh repository.

    Returns:
        The user's home folder, empty.
    """
    root = repository.root
    settings = {
        'disableAllHooks': False,
        'hooks': hook_integrity.expected_hooks(),
    }
    write_file(root, SETTINGS, _json(settings))
    marker = hook_integrity.PRE_COMMIT_MARKER
    write_file(root, HOOK, f'#!/usr/bin/env bash\n{marker}\n')
    folder = root.parent / 'home'
    folder.mkdir()
    return folder


def _paths(repository: Runner, home: Path, *, ci: bool = False) -> list[str]:
    environment = {'CI': 'true'} if ci else {}
    outcome = hook_integrity.run(
        repository.root,
        home,
        repository,
        environment=environment,
    )
    return [found.path for found in outcome.violations]


def test_expected_hooks_follow_the_spec() -> None:
    """The four registrations of §9.1, with their timeouts and commands."""
    hooks = hook_integrity.expected_hooks()
    assert list(hooks) == ['PreToolUse', 'PostToolUse', 'Stop', 'ConfigChange']
    stop = json.dumps(hooks['Stop'])
    assert '"timeout": 334' in stop
    assert (
        r'cd \"$CLAUDE_PROJECT_DIR\" && .venv/bin/python -m quality_gate '
        r'hook stop || exit 2'
    ) in stop


def test_a_complete_setup_passes(repository: Runner, home: Path) -> None:
    """Settings, local settings, user settings and commit hook all in place.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
    """
    write_file(repository.root, LOCAL, _json({'env': {'HTTP_PROXY': 'x'}}))
    write_file(home, SETTINGS, _json({'model': 'opus'}))
    outcome = hook_integrity.run(
        repository.root, home, repository, environment={}
    )
    assert (outcome.name, outcome.status) == ('hook-integrity', Status.PASS)


@pytest.mark.parametrize(
    'settings',
    [
        None,
        'not json\n',
        _json({'disableAllHooks': True}),
        _json({'disableAllHooks': False, 'hooks': {}}),
    ],
)
def test_missing_or_disabled_settings_fail(
    repository: Runner,
    home: Path,
    settings: str | None,
) -> None:
    """Settings that are missing, unreadable, disabled or edited fail.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
        settings: The project settings' text, or None for no file.
    """
    target = repository.root / SETTINGS
    target.unlink()
    if settings is not None:
        write_file(repository.root, SETTINGS, settings)
    assert _paths(repository, home) == [SETTINGS]


def test_a_changed_timeout_fails(repository: Runner, home: Path) -> None:
    """A hook given more time than the gate's is a hook changed.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
    """
    hooks = hook_integrity.expected_hooks()
    loosened = json.dumps(hooks).replace('"timeout": 334', '"timeout": 9999')
    write_file(
        repository.root,
        SETTINGS,
        f'{{"disableAllHooks": false, "hooks": {loosened}}}\n',
    )
    assert _paths(repository, home) == [SETTINGS]


@pytest.mark.parametrize(
    'local',
    [
        _json({'disableAllHooks': True}),
        _json({'hooks': {}}),
        'not json\n',
    ],
)
def test_local_settings_cannot_disable_hooks(
    repository: Runner,
    home: Path,
    local: str,
) -> None:
    """Local settings cannot turn the hooks off or replace them.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
        local: The local settings' text.
    """
    write_file(repository.root, LOCAL, local)
    assert _paths(repository, home) == [LOCAL]


@pytest.mark.parametrize('name', ['QUALITY_GATE_MAINTENANCE', 'CLAUDECODE'])
def test_local_settings_cannot_set_gate_variables(
    repository: Runner,
    home: Path,
    name: str,
) -> None:
    """Local settings cannot set the gate's variables.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
        name: A variable the gate reads.
    """
    write_file(repository.root, LOCAL, _json({'env': {name: '1'}}))
    assert _paths(repository, home) == [LOCAL]


def test_user_settings_cannot_set_gate_variables(
    repository: Runner, home: Path
) -> None:
    """The user's own settings cannot set them either.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
    """
    write_file(home, SETTINGS, _json({'env': {'QUALITY_GATE_X': '1'}}))
    assert _paths(repository, home) == ['~/.claude/settings.json']


@pytest.mark.parametrize('hook', [None, '#!/bin/sh\nexit 0\n'])
def test_a_foreign_pre_commit_hook_fails(
    repository: Runner,
    home: Path,
    hook: str | None,
) -> None:
    """A commit hook missing, or not pre-commit's, fails.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
        hook: The hook's text, or None for no hook.
    """
    (repository.root / HOOK).unlink()
    if hook is not None:
        write_file(repository.root, HOOK, hook)
    assert _paths(repository, home) == [HOOK]


def test_a_hooks_path_fails(repository: Runner, home: Path) -> None:
    """With core.hooksPath set, git would skip `.git/hooks`.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
    """
    configured = ('config', 'core.hooksPath', '.githooks')
    assert repository.git(configured).exit_code == 0
    assert _paths(repository, home) == ['.git/config']


def test_ci_skips_the_commit_hook(repository: Runner, home: Path) -> None:
    """In CI there is no local commit hook to check.

    Args:
        repository: A fresh repository.
        home: The user's home folder; the gate's hooks are in place.
    """
    (repository.root / HOOK).unlink()
    assert _paths(repository, home, ci=True) == []
