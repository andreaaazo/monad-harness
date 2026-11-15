"""What every agent tool is made of: the context it runs with, its schema base, the tool record and the
helpers more than one tool module shares (ADR-0057).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from opentelemetry import trace
from pydantic import BaseModel, ConfigDict

from agency.artifacts import keeping
from agency.config import Settings
from agency.contracts.artifact import ArtifactStore, Origin
from agency.contracts.ledger import LedgerPort
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.phase import DirectorMode
from agency.contracts.registry import StudioRules
from agency.contracts.ticket import Action, Status
from agency.workshop import craft
from agency.workshop.sandbox import Sandbox

tracer = trace.get_tracer("agency.tools")


class Refused(Exception):
    """A refused action: the reason goes back to the model, which can correct itself."""


@dataclass
class ToolContext:
    """What a tool call runs with: who calls, for which ticket and instance, with which ledger, sandbox and
    store. A closing tool sets `finished`."""

    actor: str
    project: str
    ticket_id: str
    instance: str
    ledger: LedgerPort
    sandbox: Sandbox
    index: craft.CommandIndex
    artifacts: ArtifactStore
    rules: StudioRules
    finished: Outcome | None = None
    warned_sketch: str = ""  # sha256 of the sketch already warned about: one warning per version
    mode: DirectorMode | None = None
    round: int = 1
    settings: Settings | None = None
    run: int | None = None  # the run in progress: None outside a session

    @property
    def work(self) -> Path:
        return self.sandbox.work

    @cached_property
    def finisher_outputs(self) -> tuple[str, ...]:
        """A finisher's masters: the concept is chosen, so it works only on those. Empty for other roles."""
        try:
            spec = self.ledger.spec(self.ticket_id)
        except KeyError:
            return ()
        return tuple(spec.outputs) if spec.prompt == "finisher" else ()

    def keep(self, paths: list[str], origin: Origin) -> dict[str, str]:
        """Keeps the files' current version before the event that uses it. Returns the hashes."""
        return keeping.keep(
            self.artifacts,
            self.ledger,
            self.work,
            {path: path for path in paths},
            project=self.project,
            origin=origin,
            ticket_id=self.ticket_id,
            run=self.run,
        )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Tool:
    """A tool the model can call. On resume an effect already recorded is replayed, not run again: `closes`
    is the outcome a closing tool always ends with, and `on_replay` derives the outcome from the stored result
    for a tool whose ending depends on what it chose (None: the instance stays open)."""

    name: str
    description: str
    schema: type[BaseModel]
    handler: Callable[[ToolContext, Any, str], Any]
    effect: bool = True
    strict: bool = False
    closes: OutcomeState | None = None
    on_replay: Callable[[str], Outcome | None] | None = None


def viewed(ctx: ToolContext) -> dict[str, int]:
    """The images this instance really looked at, by version: the system knows it, not the agent."""
    seen: dict[str, int] = {}
    for row in ctx.ledger.operations(ctx.instance):
        if row.tool == "view_image":
            key = json.loads(row.result_json)["key"]
            seen[key] = seen.get(key, 0) + 1
    return seen


def result_text(value: dict) -> str:
    """The text of a tool result, as the model reads it and as the resume record keeps it."""
    return json.dumps(value, ensure_ascii=False)


def replayed(ctx: ToolContext, target: Status, action: Action, ticket: str | None = None) -> bool:
    """True when the ticket (this instance's own by default) is already in `target` because this actor just
    did `action`: a replay after a crash between the ledger transition and its resume record (COR-003)."""
    ticket = ticket or ctx.ticket_id
    if ctx.ledger.status(ticket)[0] is not target:
        return False
    history = ctx.ledger.history(ticket)
    return bool(history) and history[-1].action == action.value and history[-1].actor == ctx.actor


def definition(tool: Tool) -> dict:
    schema = tool.schema.model_json_schema()
    schema.pop("title", None)
    item = {"name": tool.name, "description": tool.description, "input_schema": schema}
    if tool.strict:
        item["strict"] = True
    else:
        item["eager_input_streaming"] = True
    return item
