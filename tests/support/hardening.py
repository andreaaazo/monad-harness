"""What more than one hardening test file uses: contexts, specs, ledgers and the sandbox doubles."""

from __future__ import annotations

import itertools
import shutil
from pathlib import Path
from typing import Any

import pytest

from agency.agents.toolbox import TOOLS, Toolbox, role_tools
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.gate import Gate
from agency.contracts.ledger import (
    ConceptEntry,
)
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Completed, Sandbox
from support.concepts import open_idea
from support.rules import RULES
from support.scripted import ScriptedTransport
from support.settings import settings


def context(tmp_path: Path, actor: str = "identity-designer", ticket: str = "T-1") -> ToolContext:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    inputs = settings(tmp_path).layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True, exist_ok=True)
    return ToolContext(
        actor,
        "p",
        ticket,
        "i",
        Ledger(tmp_path / "l.sqlite"),
        Sandbox(work, ops=inputs),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )


OPERATIONS = itertools.count(1)


needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def call(ctx: ToolContext, tool_name: str, **arguments: object) -> dict:
    """Each call has its own id: with the same id, the system repeats the first outcome, as it should."""
    return Toolbox(ctx, role_tools(RULES, ctx.actor)).call(f"t{next(OPERATIONS)}", tool_name, arguments)


def spec(**extra: Any) -> TicketSpec:
    values: dict[str, Any] = {
        "title": "Segno",
        "request": "Disegna",
        "type": TicketType.PRODUCTION,
        "sender": "design-director",
        "assignee": "identity-designer",
        "outputs": ["a.md"],
        "checks": {"*.md": ["req:testo"]},
        "media": [Medium.NONE],
        "medium_why": "solo testo, nessun mezzo visivo",
    }
    return TicketSpec.model_validate(values | extra)


class IdleSandbox(Sandbox):
    """Runs nothing: what matters is what the harness writes before the sandbox starts."""

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        return Completed(1, "", "")


# Commands: a typo must not cost an exploration


class FakeSession:
    def __init__(self, gates: list[Gate], ledger: Ledger | None = None) -> None:
        self.gates = gates
        self.calls: list[tuple] = []
        self.ledger = ledger or Ledger(Path("/dev/null"))
        self.settings = Settings(_env_file=None)  # type: ignore[call-arg]

    def pending(self, _: str) -> list[Gate]:
        return self.gates

    def decide(self, *arguments: object) -> str:
        self.calls.append(arguments)
        self.gates = []
        return ""


def cli_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Data and project folders of the test's own, and no .env: the CLI builds its settings from here."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "data" / "ledger.sqlite"


def scripted_run(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> ScriptedTransport:
    """`agency run` with the real session, over scripted responses: no call leaves the machine."""
    from agency.process.session import open_session

    transport = ScriptedTransport(responses)
    monkeypatch.setattr(
        "agency.process.session.open_session",
        lambda settings, record=False: open_session(settings, transport, record=record),
    )
    return transport


BLOCK_AT_ONCE = {
    "content": [{"type": "tool_use", "id": "t1", "name": "block", "input": {"reason": "prova del tetto"}}],
    "stop_reason": "tool_use",
    "model": "claude-sonnet-5-5",
    "usage": {"input_tokens": 100, "output_tokens": 20},
}


def hold_project_lock(path: Path) -> int:
    """Hold a project lock as another engine process would: through its own open file (`flock` conflicts)."""
    import fcntl
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def busy_line(project: str) -> str:
    return f"Un altro processo sta già lavorando sul progetto {project}: attendi che finisca e riprova"


def use(ctx: ToolContext, name: str, **arguments: object) -> dict:
    """One call of one tool, whatever the role's set holds."""
    return Toolbox(ctx, [TOOLS[name]]).call(f"t{next(OPERATIONS)}", name, arguments)


def director(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "design-director", "T-0")
    ctx.settings = settings(tmp_path)
    ctx.ticket_id = ctx.ledger.open(spec(type=TicketType.DELIVERY, assignee="design-director"), "p")
    return ctx


def rating(*letters: str, passing: str = "") -> list[dict]:
    return [{"letter": letter, "first_look": "Un segno", "passes": letter in passing} for letter in letters]


def board_critic(tmp_path: Path) -> ToolContext:
    """The critic of round 1: its work folder is the board's, inside the project's."""
    ctx = context(tmp_path, "critic", "T-5")
    ctx.settings = settings(tmp_path)
    ctx.sandbox = Sandbox(ctx.work / "board/r1", ops=ctx.sandbox.ops)
    ctx.sandbox.work.mkdir(parents=True)
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptEntry(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    return ctx
