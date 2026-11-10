"""Esecuzione isolata con bubblewrap: una cartella scrivibile, nessuna rete, nessun segreto."""

from __future__ import annotations

import contextlib
import io
import os
import selectors
import signal
import subprocess
import time
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
# /dev/shm: `--dev` mounts it unsized, so it would otherwise report the host's free RAM.
SHM_BYTES = 256 * 2**20
FILE_BYTES = 2 * 2**30  # RLIMIT_FSIZE of every command: the largest file it can write or extend
# Caps of the cgroup scope every command runs in (ADR-0046). tmpfs pages written by the command count toward
# the memory cap, so /tmp and /home above are part of it.
MEMORY_MAX_BYTES = 8 * 2**30
TASKS_MAX = 512  # threads count as tasks
SCOPE_PROBE_SECONDS = 15
OUTPUT_BYTES = 8 * 2**20  # the most of each of stdout and stderr the harness keeps in memory
READ_BYTES = 64 * 1024
PIPE_BUF = 4096  # a write of at most this many bytes to a pipe that select() reported writable never blocks


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
            "--size", str(SHM_BYTES), "--tmpfs", "/dev/shm",
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
        # Its own process group, so that the kill below reaches systemd-run and bwrap (and, through bwrap's
        # --die-with-parent, everything in the sandbox) even though the command itself runs in a new session.
        proc = subprocess.Popen(
            self.argv(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        try:
            kept, outcome = _collect(proc, (stdin or "").encode("utf-8"), timeout)
        finally:
            _kill_group(proc)
        if outcome == "timeout":
            return Completed(124, "", f"tempo scaduto dopo {timeout:.0f} s")
        stdout, stderr = _text(kept[0]), _text(kept[1])
        if outcome == "overflow":
            note = f"\nuscita oltre {OUTPUT_BYTES // 2**20} MiB: comando fermato"
            return Completed(125, stdout, stderr + note)
        return Completed(proc.returncode, stdout, stderr)


def _text(data: bytearray) -> str:
    """The bytes as `text=True` read them (universal newlines), but a byte that is not UTF-8 becomes U+FFFD
    instead of raising."""
    return io.TextIOWrapper(io.BytesIO(bytes(data)), encoding="utf-8", errors="replace").read()


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    """Kill what is still running of the process group `proc` leads, and reap `proc`."""
    if proc.returncode is None:  # a reaped leader's id may already be someone else's
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        if pipe is not None:
            pipe.close()
    proc.wait()


def _collect(
    proc: subprocess.Popen[bytes], data: bytes, timeout: float
) -> tuple[tuple[bytearray, bytearray], str]:
    """Feed `data` to the command and read its two streams, keeping at most OUTPUT_BYTES of each.

    Returns the kept bytes and how it ended: "done", "timeout" or "overflow" (a stream passed the cap)."""
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    deadline = time.monotonic() + timeout
    kept = (bytearray(), bytearray())
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ, kept[0])
    selector.register(proc.stderr, selectors.EVENT_READ, kept[1])
    sent = 0
    if data:
        os.set_blocking(proc.stdin.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE)
    else:
        proc.stdin.close()
    with selector:
        while selector.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                return kept, "timeout"
            for key, _ in selector.select(left):
                if key.fileobj is proc.stdin:
                    try:
                        sent += os.write(proc.stdin.fileno(), data[sent : sent + PIPE_BUF])
                    except BrokenPipeError:  # the command stopped reading: nothing more to feed it
                        sent = len(data)
                    if sent >= len(data):
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                    continue
                chunk = os.read(key.fd, READ_BYTES)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer: bytearray = key.data
                buffer += chunk
                if len(buffer) > OUTPUT_BYTES:
                    del buffer[OUTPUT_BYTES:]
                    return kept, "overflow"
    try:
        proc.wait(max(deadline - time.monotonic(), 0))
    except subprocess.TimeoutExpired:
        return kept, "timeout"
    return kept, "done"
