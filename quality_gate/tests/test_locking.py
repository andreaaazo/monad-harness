"""Tests of the `lock` mode: only a person at a terminal writes the lock."""

import io
from pathlib import Path
from typing import override

import pytest

from quality_gate.integrity import locking
from quality_gate.integrity.lockfile import LOCK_PATH, compute_lock, render_lock
from quality_gate.model import CheckResult, GateError, Status, Violation
from quality_gate.tests.fakes import write_file

RUFF = '[tool.ruff.lint.pylint]\nmax-args = 4\n'
GATE_FILES = ('quality_gate/cli.py',)


class _Tty(io.StringIO):
    @override
    def isatty(self) -> bool:
        return True


def _console(answer: str = 'LOCK\n') -> tuple[locking.ConsoleTerminal, _Tty]:
    output = _Tty()
    return locking.ConsoleTerminal(_Tty(answer), output), output


def _passing() -> tuple[CheckResult, ...]:
    return (CheckResult('tool-versions', Status.PASS, 0, (), ''),)


def _failing() -> tuple[CheckResult, ...]:
    found = Violation('.claude/settings.json', 1, 1, 'hooks', 'no hooks')
    return (CheckResult('hook-integrity', Status.FAIL, 0, (found,), ''),)


def _repository(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('CLAUDECODE', raising=False)
    write_file(root, 'pyproject.toml', RUFF)
    write_file(root, 'quality_gate/cli.py', '"""The command line."""\n')


def _refused(
    root: Path,
    terminal: locking.ConsoleTerminal,
    pattern: str,
) -> None:
    with pytest.raises(GateError, match=pattern):
        pytest.fail(
            repr(locking.lock(root, GATE_FILES, terminal, guards=_passing)),
        )


def test_lock_refuses_without_a_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a person at a terminal there is no lock.

    Args:
        tmp_path: The repository root.
        monkeypatch: Clears the Claude Code variable.
    """
    _repository(tmp_path, monkeypatch)
    piped = locking.ConsoleTerminal(io.StringIO('LOCK\n'), _Tty())
    _refused(tmp_path, piped, 'lock needs a terminal')
    assert not (tmp_path / LOCK_PATH).exists()


def test_lock_refuses_inside_claude_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inside Claude Code the lock refuses, terminal or not.

    Args:
        tmp_path: The repository root.
        monkeypatch: Sets the variable Claude Code sets.
    """
    _repository(tmp_path, monkeypatch)
    monkeypatch.setenv('CLAUDECODE', '1')
    terminal, _output = _console()
    _refused(tmp_path, terminal, 'lock cannot run inside Claude Code')


def test_lock_refuses_when_a_guard_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gate whose hooks or tools are not in place cannot be locked.

    Args:
        tmp_path: The repository root.
        monkeypatch: Clears the Claude Code variable.
    """
    _repository(tmp_path, monkeypatch)
    terminal, _output = _console()
    with pytest.raises(GateError, match='hook-integrity FAIL'):
        pytest.fail(
            repr(locking.lock(tmp_path, GATE_FILES, terminal, guards=_failing)),
        )


def test_lock_shows_changes_and_writes_on_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The person sees what changed, types LOCK, and the lock is written.

    Args:
        tmp_path: The repository root.
        monkeypatch: Clears the Claude Code variable.
    """
    _repository(tmp_path, monkeypatch)
    old = compute_lock(tmp_path, GATE_FILES)
    write_file(tmp_path, LOCK_PATH, render_lock(old))
    write_file(tmp_path, 'pyproject.toml', RUFF.replace('4', '5'))
    terminal, output = _console()
    assert locking.lock(tmp_path, GATE_FILES, terminal, guards=_passing) == 0
    assert output.getvalue().startswith('tables tool.ruff changed\nType LOCK')
    written = (tmp_path / LOCK_PATH).read_text(encoding='utf-8')
    assert written == render_lock(compute_lock(tmp_path, GATE_FILES))


def test_an_unchanged_lock_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With nothing changed the person reads it before answering.

    Args:
        tmp_path: The repository root.
        monkeypatch: Clears the Claude Code variable.
    """
    _repository(tmp_path, monkeypatch)
    write_file(
        tmp_path, LOCK_PATH, render_lock(compute_lock(tmp_path, GATE_FILES))
    )
    terminal, output = _console()
    assert locking.lock(tmp_path, GATE_FILES, terminal, guards=_passing) == 0
    assert output.getvalue().startswith('no change\n')


@pytest.mark.parametrize('answer', ['lock\n', 'y\n', '', 'LOCK \n'])
def test_any_other_answer_aborts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
) -> None:
    """Only the exact word writes the lock; anything else leaves it alone.

    Args:
        tmp_path: The repository root.
        monkeypatch: Clears the Claude Code variable.
        answer: What the person typed.
    """
    _repository(tmp_path, monkeypatch)
    write_file(tmp_path, LOCK_PATH, 'not json\n')
    terminal, output = _console(answer)
    assert locking.lock(tmp_path, GATE_FILES, terminal, guards=_passing) == 2
    assert output.getvalue().startswith('lock missing\n')
    assert output.getvalue().endswith('nothing written\n')
    assert (tmp_path / LOCK_PATH).read_text(encoding='utf-8') == 'not json\n'


def test_the_real_terminal_needs_two_ttys() -> None:
    """The console counts as a terminal only when both streams are ttys."""
    assert locking.ConsoleTerminal(_Tty(), _Tty()).interactive()
    assert not locking.ConsoleTerminal(io.StringIO(), _Tty()).interactive()
    assert not locking.ConsoleTerminal(_Tty(), io.StringIO()).interactive()
