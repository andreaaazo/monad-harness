"""What changed, as git sees it (SPEC §7.2).

`changed` compares the working tree, staged and unstaged, with the merge-base
of a reference and HEAD, and adds the untracked files git does not ignore.
Every path counts here, Python or not, deleted or not: the ratchet decides
from all of them. A rename counts as its old path deleted and its new one
added, so a module moved into the docs still runs the suite.
"""

from quality_gate.execution import Runner
from quality_gate.model import GateError

_ADDED_COPIED_MODIFIED_RENAMED = '--diff-filter=ACMR'


def changed_paths(runner: Runner, base: str) -> tuple[str, ...] | None:
    """List every file that differs from the merge-base of `base` and HEAD.

    Args:
        runner: A runner rooted in the repository.
        base: The reference to compare with, such as `HEAD`.

    Returns:
        Sorted root-relative paths, or None in a repository with no commit,
        where everything counts as changed.

    Raises:
        GateError: git cannot resolve `base`.
    """
    if runner.git(('rev-parse', '--verify', '--quiet', 'HEAD')).exit_code:
        return None
    found = runner.git(('merge-base', base, 'HEAD'))
    if found.exit_code:
        message = f'unknown base: {base}'
        raise GateError(message)
    diff = ('diff', '--name-only', '-z', '--no-renames')
    changed = _names(runner, (*diff, found.stdout.strip()))
    untracked = _names(
        runner, ('ls-files', '-z', '--others', '--exclude-standard')
    )
    return tuple(sorted({*changed, *untracked}))


def staged_paths(runner: Runner) -> tuple[str, ...]:
    """List the files staged for the next commit, added or modified.

    Args:
        runner: A runner rooted in the repository.

    Returns:
        Sorted root-relative paths.
    """
    staged = (
        'diff',
        '--cached',
        '--name-only',
        '-z',
        _ADDED_COPIED_MODIFIED_RENAMED,
    )
    return tuple(sorted(_names(runner, staged)))


def _names(runner: Runner, arguments: tuple[str, ...]) -> set[str]:
    listed = runner.git(arguments)
    if listed.exit_code:
        command, reason = arguments[0], listed.stderr.strip()
        message = f'git {command} failed: {reason}'
        raise GateError(message)
    return {name for name in listed.stdout.split('\0') if name}
