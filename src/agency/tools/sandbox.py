"""Esecuzione isolata con bubblewrap: una cartella scrivibile, nessuna rete, nessun segreto."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

JOB = "/job"
OPS = "/ops"
QA_MOUNT = "/opt/agency-qa"
ETC_ALLOWED = ("/etc/ld.so.cache", "/etc/fonts", "/etc/alternatives", "/etc/ssl", "/etc/mime.types")
HOME = "/home/studio"
# Size bounds: of the RAM-backed tmpfs mounts, and of each file a command writes (not of the disk as a whole).
TMP_BYTES = 2 * 2**30
HOME_BYTES = 256 * 2**20
FILE_BYTES = 2 * 2**30  # RLIMIT_FSIZE of every command: the largest file it can write or extend
# Caps of the cgroup scope every command runs in (ADR-0046). tmpfs pages written by the command count toward
# the memory cap, so /tmp and /home above are part of it.
MEMORY_MAX_BYTES = 8 * 2**30
TASKS_MAX = 512  # threads count as tasks
SCOPE_PROBE_SECONDS = 15


@dataclass(frozen=True)
class Completed:
    code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


class SandboxUnavailable(RuntimeError):
    """The sandbox cannot start without its cgroup caps. A RuntimeError, so that `Toolbox.call` hands the
    reason to the model as a refused tool call instead of reporting a tool crash."""


def scope_prefix() -> list[str]:
    """The command that puts what follows it in a transient cgroup scope with memory and task caps."""
    return [
        "systemd-run", "--user", "--scope", "--quiet",
        "-p", f"MemoryMax={MEMORY_MAX_BYTES}",
        "-p", "MemorySwapMax=0",
        "-p", f"TasksMax={TASKS_MAX}",
        "--",
    ]  # fmt: skip


def scope_problem() -> str | None:
    """None if a capped scope can be created now, else the reason.

    A probe that runs before the command, never a reading of the command's own exit code or output, which
    model-written code could fake."""
    try:
        done = subprocess.run(
            [*scope_prefix(), "true"], capture_output=True, text=True, timeout=SCOPE_PROBE_SECONDS
        )
    except FileNotFoundError:
        return "systemd-run non esiste su questa macchina"
    except subprocess.TimeoutExpired:
        return f"systemd-run non risponde entro {SCOPE_PROBE_SECONDS} s"
    except OSError as exc:
        return f"systemd-run non parte: {exc}"
    if done.returncode == 0:
        return None
    said = (done.stderr or done.stdout).strip()
    return f"systemd-run non crea lo scope (uscita {done.returncode}): {said[:300]}"


class Sandbox:
    def __init__(
        self,
        work: Path,
        toolchain: Path | None = None,
        read_only: tuple[Path, ...] = (),
        ops: Path | None = None,
    ) -> None:
        """`ops` holds the files the harness writes for the sandbox to run. It is bound read-only at /ops,
        outside the writable /job, so sandboxed code cannot change what the harness trusts (ADR-0044)."""
        self.work = work.resolve()
        self.toolchain = toolchain
        self.read_only = read_only
        self.ops = ops
        self._scope_checked = False

    def argv(self, command: list[str]) -> list[str]:
        args = [
            *scope_prefix(),
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64",
            "--symlink", "usr/sbin", "/sbin",
            "--proc", "/proc",
            "--dev", "/dev",
            "--size", str(TMP_BYTES), "--tmpfs", "/tmp",
            "--size", str(HOME_BYTES), "--tmpfs", "/home",
            "--dir", HOME,
            "--bind", str(self.work), JOB,
            "--chdir", JOB,
            "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "HOME", HOME,
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "CLAUDE_PROJECT_DIR", "/tmp",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--die-with-parent",
            "--new-session",
        ]  # fmt: skip
        if self.ops is not None:
            args += ["--ro-bind", str(self.ops), OPS]
        for path in ETC_ALLOWED:
            if Path(path).exists():
                args += ["--ro-bind", path, path]
        fonts = Path.home() / ".local/share/fonts"
        if fonts.exists():
            args += ["--ro-bind", str(fonts), f"{HOME}/.local/share/fonts"]
        scripts = Path(__file__).resolve().parents[1] / "qa/scripts"
        args += ["--ro-bind", str(scripts), QA_MOUNT]
        if self.toolchain and self.toolchain.exists():
            args += ["--ro-bind", str(self.toolchain), str(self.toolchain)]
        for path in self.read_only:
            args += ["--ro-bind", str(path), str(path)]
        return [*args, "prlimit", f"--fsize={FILE_BYTES}", "--", *command]

    def python(self) -> str:
        if self.toolchain:
            candidate = self.toolchain / "venv/bin/python"
            if candidate.exists():
                return str(candidate)
        return "python3"

    def run(self, command: list[str], timeout: float = 120, stdin: str | None = None) -> Completed:
        if not self._scope_checked:
            why = scope_problem()
            if why:
                raise SandboxUnavailable(f"la sandbox non parte senza i limiti di memoria e processi: {why}")
            self._scope_checked = True
        try:
            result = subprocess.run(
                self.argv(command), capture_output=True, text=True, timeout=timeout, input=stdin
            )
        except subprocess.TimeoutExpired:
            return Completed(124, "", f"tempo scaduto dopo {timeout:.0f} s")
        return Completed(result.returncode, result.stdout, result.stderr)
