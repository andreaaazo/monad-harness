"""How a tool's exit code and output become a check's result (SPEC §7.3).

The verdict comes from the exit code; the details come from the output. A
tool that names nothing but says it failed still fails, and an exit code or
an output the check does not expect is an error, which counts as a failure.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from quality_gate.execution import Completed, Runner, ToolError
from quality_gate.model import CheckResult, Status, Violation

type Parser = Callable[[str, Path], tuple[Violation, ...]]
type Stream = Literal['stdout', 'stderr']


@dataclass(frozen=True, slots=True)
class CheckInput:
    """What a check works on.

    Attributes:
        runner: The runner of this run of the gate.
        files: The root-relative Python files to check.
    """

    runner: Runner
    files: tuple[str, ...]


type Check = Callable[[CheckInput], CheckResult]


@dataclass(frozen=True, slots=True)
class ToolCheck:
    """A check made of one run of one tool on the given files.

    Attributes:
        name: The check's name, as SPEC §7.4 lists it.
        tool: The tool's executable, in the interpreter's scripts folder.
        options: The arguments before the files.
        parse: Reads the tool's standard output into violations, and
            raises ValueError when it cannot.
        failing: The exit codes that mean "found something".
        stream: The output that holds the findings: pydoclint writes them
            to standard error.
    """

    name: str
    tool: str
    options: tuple[str, ...]
    parse: Parser
    failing: frozenset[int]
    stream: Stream = 'stdout'

    def findings(self, completed: Completed) -> str:
        """Pick the output that holds the tool's findings.

        Args:
            completed: What the tool gave back.

        Returns:
            Its standard output, or its standard error for `stderr`.
        """
        if self.stream == 'stderr':
            return completed.stderr
        return completed.stdout


def judge(check: ToolCheck, completed: Completed, root: Path) -> CheckResult:
    """Turn a finished tool into the check's result.

    Args:
        check: The check that ran the tool.
        completed: What the tool gave back.
        root: The repository root, for the paths the tool reports.

    Returns:
        PASS, FAIL or ERROR, with the violations and the raw output.
    """
    raw = f'{completed.stdout}{completed.stderr}'
    expected = completed.exit_code in check.failing | {0}
    try:
        found = (
            check.parse(check.findings(completed), root) if expected else None
        )
    except ValueError:
        found = None
    if found is None:
        return _outcome(check, Status.ERROR, seconds=completed.seconds, raw=raw)
    clean = completed.exit_code == 0 and not found
    status = Status.PASS if clean else Status.FAIL
    return CheckResult(check.name, status, completed.seconds, found, raw)


def run_tool_check(check: ToolCheck, given: CheckInput) -> CheckResult:
    """Run the check's tool on the given files and judge it.

    With no file the tool does not run: without paths, Ruff and
    basedpyright would check the whole project.

    Args:
        check: The check to run.
        given: The runner and the files.

    Returns:
        The check's result.
    """
    if not given.files:
        return _outcome(check, Status.PASS, seconds=0, raw='')
    arguments = (*check.options, *(f'./{name}' for name in given.files))
    started = time.perf_counter()
    try:
        completed = given.runner.tool(check.tool, arguments)
    except ToolError as error:
        seconds = time.perf_counter() - started
        return _outcome(check, Status.ERROR, seconds=seconds, raw=str(error))
    return judge(check, completed, given.runner.root)


def relative_path(root: Path, reported: str) -> str:
    """Bring a path as a tool printed it back to the root-relative form.

    Args:
        root: The repository root.
        reported: The path the tool printed: absolute, `./`-prefixed or
            relative to the root.

    Returns:
        The root-relative POSIX path.

    Raises:
        ValueError: The path is outside the root.
    """
    path = Path(reported)
    if not path.is_absolute():
        return PurePosixPath(reported).as_posix()
    for base in (root, root.resolve()):
        if path.is_relative_to(base):
            return path.relative_to(base).as_posix()
    message = f'outside the root {root}: {reported}'
    raise ValueError(message)


def _outcome(
    check: ToolCheck,
    status: Status,
    *,
    seconds: float,
    raw: str,
) -> CheckResult:
    return CheckResult(check.name, status, seconds, (), raw)
