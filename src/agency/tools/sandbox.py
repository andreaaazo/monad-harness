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


@dataclass(frozen=True)
class Completed:
    code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


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

    def argv(self, command: list[str]) -> list[str]:
        args = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64",
            "--symlink", "usr/sbin", "/sbin",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--tmpfs", "/home",
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
        return [*args, *command]

    def python(self) -> str:
        if self.toolchain:
            candidate = self.toolchain / "venv/bin/python"
            if candidate.exists():
                return str(candidate)
        return "python3"

    def run(self, command: list[str], timeout: float = 120, stdin: str | None = None) -> Completed:
        try:
            result = subprocess.run(
                self.argv(command), capture_output=True, text=True, timeout=timeout, input=stdin
            )
        except subprocess.TimeoutExpired:
            return Completed(124, "", f"tempo scaduto dopo {timeout:.0f} s")
        return Completed(result.returncode, result.stdout, result.stderr)
