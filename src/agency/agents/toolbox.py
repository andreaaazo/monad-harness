"""What the model can do: typed tools, signed by the harness, never a shell."""

from __future__ import annotations

from pydantic import ValidationError

from agency import registry
from agency.contracts.outcome import Outcome
from agency.contracts.ticket import (
    TicketSpec,
    TicketType,
)
from agency.ledger import ForbiddenAction, IllegalTransition
from agency.qa import evidence
from agency.studio.exploration import tools as exploration
from agency.studio.exploration.tools import EXPLORE, PLAN
from agency.studio.presentation import tools as presentation
from agency.studio.presentation.tools import PRESENT
from agency.studio.proposal.tools import PROPOSAL
from agency.studio.refinement import tools as refinement
from agency.studio.selection import tools as selection
from agency.studio.selection.tools import BOARD, SELECT
from agency.toolkit import closing, craft, files, review
from agency.toolkit.base import (
    Refused,
    Tool,
    ToolContext,
    definition,
    result_text,
    tracer,
)
from agency.workshop.files import (
    OutsidePerimeter,
    clip,
)

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        *files.TOOLS,
        *craft.TOOLS,
        *review.TOOLS,
        *refinement.TOOLS,
        *closing.TOOLS,
        *exploration.TOOLS,
        *selection.TOOLS,
        *presentation.TOOLS,
    )
}
BASE = ["read_file", "list_files", "write_file", "read_skill", "view_image", "render", "deliver", "block"]
AUTHOR = ["craft_search", "craft_describe", "craft_run", "compute", "export_master", "run_check", "observe"]
AUTHOR += ["record_requirement"]
REVIEWER = ["run_check", "observe", "judge", "record_requirement"]
DIRECTOR = ["open_ticket", "accept_ticket", "rework_ticket", "hand_off", "observe", "judge", "run_check"]
DIRECTOR += ["reject_concept"]


KIND_TOOLS = {
    "director": BASE + DIRECTOR,
    "router": BASE + DIRECTOR,
    "reviewer": BASE + REVIEWER,
    "author": BASE + AUTHOR,
}


def _without_craft(role: str, names: list[str]) -> list[str]:
    """A role that lists no Craft app gets no craft_* tool, whatever set it is given."""
    if registry.ROLES[role]["craft"]:
        return names
    return [name for name in names if not name.startswith("craft_")]


def role_tools(role: str) -> list[Tool]:
    names = _without_craft(role, KIND_TOOLS[registry.ROLES[role]["tools"]])
    return [TOOLS[name] for name in sorted(names)]


def tools_for(role: str, spec: TicketSpec, mode: str = "") -> list[Tool]:
    """The set depends on the phase: who looks for the idea cannot draw, and who draws cannot finish."""
    names = {"plan": PLAN, "select": SELECT, "present": PRESENT}.get(mode)
    if names is None and spec.prompt == "critic-board":
        names = BOARD
    if names is None and spec.type is TicketType.SKETCH:
        names = EXPLORE
    if names is None and spec.type is TicketType.PROPOSAL:
        names = PROPOSAL
    if not names:
        return role_tools(role)
    return [TOOLS[name] for name in sorted(_without_craft(role, names))]


class Toolbox:
    """One instance's tools. `call` runs one: an effect already recorded is replayed, not repeated, and a
    failure goes back to the model as a refused result instead of ending work already paid for."""

    def __init__(self, context: ToolContext, tools: list[Tool] | None = None) -> None:
        self.context = context
        # The set does not change during the instance: changing it would invalidate the prompt cache.
        chosen = tools if tools is not None else role_tools(context.actor)
        self.tools = {tool.name: tool for tool in chosen}
        self._definitions = [definition(tool) for tool in self.tools.values()]

    def definitions(self) -> list[dict]:
        return self._definitions

    def call(self, tool_use_id: str, name: str, raw: dict) -> dict:
        ctx = self.context
        operation_id = f"{ctx.instance}:{tool_use_id}"
        tool = self.tools.get(name)
        if tool is None:
            return self._result(tool_use_id, f"strumento non disponibile per {ctx.actor}: {name}", True)
        if tool.effect:
            stored = ctx.ledger.operation(operation_id)
            if stored is not None:  # on resume, an effect that already happened is not repeated
                self._restore(name, stored)
                return self._result(tool_use_id, stored, False)
        with tracer.start_as_current_span("tool.call") as span:
            span.set_attributes({"agency.tool": name, "agency.instance": ctx.instance})
            try:
                arguments = tool.schema.model_validate(raw)
                value = tool.handler(ctx, arguments, operation_id)
            except ValidationError as exc:
                return self._result(tool_use_id, f"input non valido: {clip(str(exc), 800)}", True)
            except (
                Refused,
                OutsidePerimeter,
                ForbiddenAction,
                IllegalTransition,
                evidence.EvidenceRefused,
                FileNotFoundError,
                ValueError,
                RuntimeError,
                KeyError,
            ) as exc:
                span.set_attribute("agency.refused", True)
                return self._result(tool_use_id, str(exc), True)
            except Exception as exc:  # a tool failure must not bring down work already paid for
                span.record_exception(exc)
                detail = clip(f"{type(exc).__name__}: {exc}", 500)
                return self._result(tool_use_id, f"{name} non è riuscito: {detail}", True)
        if isinstance(value, list):
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": value}
        text = result_text(value)
        if tool.effect and ctx.ledger.operation(operation_id) is None:  # else the handler recorded it already
            ctx.ledger.record_operation(operation_id, ctx.instance, name, text)
        return self._result(tool_use_id, text, False)

    def _restore(self, name: str, stored: str) -> None:
        """On resume, a closing tool that already ran closes again with the same outcome."""
        tool = self.tools[name]
        if tool.closes is not None:
            self.context.finished = Outcome(state=tool.closes, note="ripreso dopo un'interruzione")
        elif tool.on_replay is not None:
            outcome = tool.on_replay(stored)
            if outcome is not None:
                self.context.finished = outcome

    @staticmethod
    def _result(tool_use_id: str, text: str, is_error: bool) -> dict:
        block: dict = {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}
        if is_error:
            block["is_error"] = True
        return block
