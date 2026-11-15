"""The sandbox's contract with the engine: where the work and the inputs appear inside it, what a command
leaves, and the port the tools and the checks reach it through (ADR-0058). `agency.workshop.sandbox`
implements it with bwrap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

JOB = "/job"
OPS = "/ops"


@dataclass(frozen=True)
class Completed:
    """A finished command: its exit code and its two streams, as text."""

    code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Both streams, stdout first."""
        return self.stdout + self.stderr


class SandboxPort(Protocol):
    """A command runner closed in one work folder."""

    @property
    def work(self) -> Path: ...

    @property
    def ops(self) -> Path | None: ...

    def run(self, command: list[str], timeout: float = 120) -> Completed: ...

    def with_mount(self, source: Path, target: str) -> SandboxPort: ...

    def python(self) -> str: ...
