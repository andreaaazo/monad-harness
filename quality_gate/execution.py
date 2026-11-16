"""The only module of the gate that launches processes (SPEC §7.3).

Every process gets a list of arguments and no shell, the repository root as
its working folder, a cleaned environment and a timeout. The Python tools
come from the interpreter's scripts folder, never from PATH; git, which is
no Python package, comes from the cleaned environment's PATH (ADR-0060).
"""

import os
import shutil
import subprocess
import sysconfig
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ALLOWED_VARIABLES: Final = (
    'PATH',
    'HOME',
    'LANG',
    'LC_ALL',
    'TMPDIR',
    'VIRTUAL_ENV',
)


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
        return self._run(executable, arguments)

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
        return self._run(Path(found), arguments)

    def _run(self, executable: Path, arguments: Sequence[str]) -> Completed:
        started = time.perf_counter()
        try:
            finished = subprocess.run(
                [str(executable), *arguments],
                cwd=self.root,
                env=dict(self.environment),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            seconds = format(self.timeout, 'g')
            message = f'timeout after {seconds}s'
            raise ToolError(message) from error
        except OSError as error:
            message = f'cannot run {executable}: {error}'
            raise ToolError(message) from error
        return Completed(
            exit_code=finished.returncode,
            stdout=finished.stdout,
            stderr=finished.stderr,
            seconds=time.perf_counter() - started,
        )


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
