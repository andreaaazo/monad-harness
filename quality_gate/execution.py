"""The only module of the gate that launches processes (SPEC §7.3).

Every process gets a list of arguments and no shell, the repository root as
its working folder, a cleaned environment and a timeout. The Python tools
come from the interpreter's scripts folder, never from PATH; git, which is
no Python package, comes from the cleaned environment's PATH (ADR-0060).

Each process starts in a session of its own, so a timeout stops the tool and
every process it started. A session of its own also keeps the terminal's
Ctrl-C from reaching the tool: when the gate is interrupted or terminated
while it waits, it kills the tool's group itself before it stops. The
output goes to files in a temporary folder outside the repository, read
once the process has ended.
"""

import contextlib
import os
import shutil
import signal
import subprocess
import sysconfig
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import IO, Final

ALLOWED_VARIABLES: Final = (
    'PATH',
    'HOME',
    'LANG',
    'LC_ALL',
    'TMPDIR',
    'VIRTUAL_ENV',
)
# Git's own variables: inside a commit hook git may use another index, and
# only git receives them (plan B, B6).
GIT_ONLY_VARIABLES: Final = ('GIT_INDEX_FILE',)


class ToolError(Exception):
    """A tool that gave no answer: missing, unable to start, or too slow."""


@dataclass(frozen=True, slots=True)
class Completed:
    """What a finished process gave back.

    Attributes:
        exit_code: The process's exit code.
        stdout: Its standard output, decoded as UTF-8.
        stderr: Its standard error, decoded as UTF-8.
        seconds: How long it ran.
    """

    exit_code: int
    stdout: str
    stderr: str
    seconds: float


def clean_environment(
    source: Mapping[str, str],
    passthrough: Sequence[str],
) -> dict[str, str]:
    """Keep only the variables a tool may see (SPEC §7.3).

    Args:
        source: The caller's environment.
        passthrough: The variables of `env_passthrough`.

    Returns:
        The fixed variables and the passthrough ones that `source` holds.
    """
    kept = (*ALLOWED_VARIABLES, *passthrough)
    return {name: source[name] for name in kept if name in source}


@dataclass(frozen=True, slots=True)
class Runner:
    """Launches the tools of one run of the gate.

    Attributes:
        root: The repository root, every process's working folder.
        scripts: The folder the Python tools come from.
        environment: The only variables every process receives.
        timeout: The seconds after which a process is stopped.
    """

    root: Path
    scripts: Path
    environment: Mapping[str, str]
    timeout: float

    def tool(self, name: str, arguments: Sequence[str]) -> Completed:
        """Run a Python tool from the scripts folder.

        Args:
            name: The tool's executable name.
            arguments: Its arguments.

        Returns:
            What the tool gave back.

        Raises:
            ToolError: The executable is not in the scripts folder.
        """
        executable = self.scripts / name
        if not executable.is_file():
            message = f'missing executable: {executable}'
            raise ToolError(message)
        return self._run(executable, arguments, self.environment)

    def git(self, arguments: Sequence[str]) -> Completed:
        """Run git, found on the environment's PATH.

        Args:
            arguments: git's arguments.

        Returns:
            What git gave back.

        Raises:
            ToolError: git is not on PATH, or there is no PATH.
        """
        found = shutil.which('git', path=self.environment.get('PATH', ''))
        if found is None:
            message = 'missing executable: git'
            raise ToolError(message)
        own = {
            name: os.environ[name]
            for name in GIT_ONLY_VARIABLES
            if name in os.environ
        }
        return self._run(Path(found), arguments, {**self.environment, **own})

    def with_environment(self, extra: Mapping[str, str]) -> 'Runner':
        """Copy the runner, with more variables for its processes.

        Args:
            extra: The variables to add, such as a coverage data file.

        Returns:
            A runner like this one whose processes also see `extra`.
        """
        environment = {**self.environment, **extra}
        return replace(self, environment=environment)

    def _run(
        self,
        executable: Path,
        arguments: Sequence[str],
        environment: Mapping[str, str],
    ) -> Completed:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory() as folder:
            exit_code, stdout, stderr = self._capture(
                [str(executable), *arguments],
                environment,
                Path(folder),
            )
        return Completed(
            exit_code, stdout, stderr, time.perf_counter() - started
        )

    def _capture(
        self,
        command: list[str],
        environment: Mapping[str, str],
        folder: Path,
    ) -> tuple[int, str, str]:
        out_path, err_path = folder / 'stdout', folder / 'stderr'
        with (
            out_path.open('wb') as out,
            err_path.open('wb') as err,
        ):
            exit_code = self._spawn(command, environment, (out, err))
        return exit_code, _decoded(out_path), _decoded(err_path)

    def _spawn(
        self,
        command: list[str],
        environment: Mapping[str, str],
        outputs: tuple[IO[bytes], IO[bytes]],
    ) -> int:
        try:
            with subprocess.Popen(
                command,
                cwd=self.root,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=outputs[0],
                stderr=outputs[1],
                start_new_session=True,
            ) as process:
                return self._wait(process)
        except OSError as error:
            message = f'cannot run {command[0]}: {error}'
            raise ToolError(message) from error

    def _wait(self, process: subprocess.Popen[bytes]) -> int:
        try:
            return process.wait(timeout=self.timeout)
        except BaseException as error:
            # A timeout, a Ctrl-C or a SIGTERM: the tool dies first.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            if not isinstance(error, subprocess.TimeoutExpired):
                raise
            seconds = format(self.timeout, 'g')
            message = f'timeout after {seconds}s'
            raise ToolError(message) from error


def _decoded(path: Path) -> str:
    return path.read_bytes().decode('utf-8', 'replace')


def runner_for(
    root: Path,
    passthrough: Sequence[str],
    timeout: float,
) -> Runner:
    """Build the runner of one run of the gate.

    Args:
        root: The repository root.
        passthrough: The variables of `env_passthrough`.
        timeout: The seconds after which a process is stopped.

    Returns:
        A runner on the interpreter's scripts folder and a clean environment.
    """
    return Runner(
        root=root,
        scripts=Path(sysconfig.get_path('scripts')),
        environment=clean_environment(os.environ, passthrough),
        timeout=timeout,
    )
