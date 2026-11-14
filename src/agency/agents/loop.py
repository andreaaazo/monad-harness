"""The loop of one agent instance: one ticket, one append-only history, no waiting."""

from __future__ import annotations

import contextlib

from opentelemetry import trace

from agency import registry
from agency.agents import prompts
from agency.agents.toolbox import Toolbox, ToolContext, tools_for
from agency.agents.transcript import Transcript
from agency.config import Settings
from agency.contracts import phase
from agency.contracts.artifact import ArtifactStore
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import RUNNABLE, Action, TicketSpec
from agency.gateway import CallContext, ModelGateway, ModelRequest, ModelResponse
from agency.ledger import IllegalTransition, Ledger
from agency.tools.craft import CommandIndex
from agency.tools.files import ensure_dir_under
from agency.tools.sandbox import Sandbox

tracer = trace.get_tracer("agency.agents")
# A turn's output budget. A turn cut off at it is asked again once with the API's ceiling.
MAX_TOKENS = 32000
API_MAX_TOKENS = 128000


def _after_fallback(content: list[dict]) -> list[dict]:
    """Keep what the serving model continues from after a mid-output server-side fallback.

    Before the last `fallback` block only text, `fallback` and paired server-tool blocks stay: the declined
    attempt's thinking and tool calls are not continuation context, and the loop must not run them. Blocks
    after the boundary stay as they are."""
    boundary = max((i for i, block in enumerate(content) if block.get("type") == "fallback"), default=None)
    if boundary is None:
        return content
    answered = {block["tool_use_id"] for block in content if "tool_use_id" in block}
    uses = {block["id"] for block in content if block.get("type") == "server_tool_use"}

    def kept(block: dict) -> bool:
        kind = block.get("type")
        if kind in ("text", "fallback"):
            return True
        if kind == "server_tool_use":
            return block["id"] in answered
        return block.get("tool_use_id") in uses

    return [block for i, block in enumerate(content) if i > boundary or kept(block)]


# The closing tools the reminder offers, in the order it names them; it names those the current phase has.
# reject_concept also closes an instance, but the reminder does not offer it (tests/test_agent_flow.py).
CLOSING = (
    "deliver",
    "hand_off",
    "plan_exploration",
    "submit_concept",
    "select_concepts",
    "draft_presentation",
    "present_concepts",
    "block",
)


class AgentRunner:
    """Runs one agent instance on a ticket until a closing tool ends it or the loop blocks the ticket.

    An interrupted instance resumes from its transcript."""

    def __init__(
        self,
        gateway: ModelGateway,
        ledger: Ledger,
        settings: Settings,
        index: CommandIndex,
        artifacts: ArtifactStore,
    ) -> None:
        self.gateway = gateway
        self.ledger = ledger
        self.settings = settings
        self.index = index
        self.artifacts = artifacts

    def run(
        self, ticket_id: str, attempt: int = 1, rework_note: str = "", mode: str = "", exploration: int = 0
    ) -> Outcome:
        """`mode` is a director phase on the same ticket: plan, select or present.

        `exploration` is the round of ideas the work belongs to, when it differs from the attempt.
        """
        spec = self.ledger.spec(ticket_id)
        project = self.ledger.project_of(ticket_id)
        folder = parse_project_name(project)  # a name read back from the registry is checked again (COR-013)
        role = spec.assignee
        instance = phase.instance(ticket_id, attempt, mode)
        transcript = Transcript(self.settings.layout.transcript(folder, instance))
        finished = transcript.outcome()
        if finished is not None:  # a resumed run never redoes an instance that already closed
            return finished
        root = self.settings.work_dir(folder)
        root.mkdir(parents=True, exist_ok=True)
        if spec.workspace:
            ensure_dir_under(root, spec.workspace)  # a link at any component is refused before bwrap binds it
        work = root / spec.workspace
        inputs = self.settings.layout.ops_inputs(folder, instance)  # its parent holds the records (ADR-0044)
        inputs.mkdir(parents=True, exist_ok=True)
        prompt = phase.of(role, spec.prompt, mode)
        toolbox = Toolbox(
            ToolContext(
                actor=role,
                project=project,
                ticket_id=ticket_id,
                instance=instance,
                ledger=self.ledger,
                sandbox=Sandbox(work, self.settings.toolchain_dir, ops=inputs),
                index=self.index,
                artifacts=self.artifacts,
                mode=mode,
                round=exploration or attempt,
                settings=self.settings,
                run=self.gateway.run,
            ),
            tools_for(role, spec, mode),
        )
        context = CallContext(project, ticket_id, role, instance, phase=prompt)
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attributes(
                {"agency.ticket": ticket_id, "agency.role": role, "agency.instance": instance}
            )
            outcome = self._loop(spec, prompt, context, toolbox, transcript, rework_note)
            span.set_attribute("agency.outcome", outcome.state.value)
        transcript.finish(outcome)
        return outcome

    def _loop(
        self,
        spec: TicketSpec,
        prompt: str,
        context: CallContext,
        toolbox: Toolbox,
        transcript: Transcript,
        rework_note: str,
    ) -> Outcome:
        role = spec.assignee
        config = registry.ROLES[role]
        choice = self.ledger.project(context.project)  # the client's model and effort override the role's
        system = [
            {"type": "text", "text": prompts.system_prompt(prompt), "cache_control": {"type": "ephemeral"}}
        ]
        messages = transcript.messages()
        if not messages:
            first = {"role": "user", "content": prompts.packet(self.ledger, context.ticket_id, rework_note)}
            transcript.append(first)
            messages.append(first)
        previous: ModelResponse | None = None
        reminded = False
        paused = False
        limit = MAX_TOKENS
        while True:
            if messages[-1]["role"] == "assistant" and not paused:  # interrupted after a model turn
                content = messages[-1]["content"]
                if any(block.get("type") == "tool_use" for block in content):
                    self._run_tools(content, toolbox, transcript, messages)
                    if toolbox.context.finished is not None:
                        return toolbox.context.finished
                elif not content or content[-1].get("type") != "server_tool_use":
                    nudge = {"role": "user", "content": self._reminder(toolbox)}
                    transcript.append(nudge)
                    messages.append(nudge)
                    reminded = True
            paused = False
            request = ModelRequest(
                model=choice.model if choice and choice.model else config["model"],
                effort=(choice.effort if choice and choice.effort else "") or spec.effort or config["effort"],
                system=system,
                messages=messages,
                tools=toolbox.definitions(),
                max_tokens=limit,
            )
            response = self.gateway.call(context, request, previous)
            previous = response
            if response.stop_reason == "refusal":
                return self._block(context, role, f"rifiuto del modello: {response.stop_details}")
            if response.stop_reason == "max_tokens":
                if limit > MAX_TOKENS:
                    return self._block(context, role, "risposta troncata due volte")
                limit = API_MAX_TOKENS  # the cut-off answer never enters the history: ask again, once
                continue
            if response.stop_reason == "model_context_window_exceeded":
                # A full window does not shrink on a retry, and the cut-off turn never enters the history.
                return self._block(context, role, "risposta troncata dalla finestra di contesto")
            limit = MAX_TOKENS
            content = _after_fallback(response.content)
            unanswered = any(block.get("type") == "tool_use" for block in content)
            if response.stop_reason != "tool_use" and unanswered:
                # A turn holding a tool call enters the append-only history only when its tools run.
                reason = f"risposta interrotta ({response.stop_reason}) con uno strumento senza risultato"
                return self._block(context, role, reason)
            assistant = {"role": "assistant", "content": content}
            if content is response.content:
                transcript.append(assistant, request_id=response.request_id)
            else:
                transcript.append(assistant, request_id=response.request_id, raw=response.content)
            messages.append(assistant)
            if response.stop_reason == "tool_use":
                self._run_tools(content, toolbox, transcript, messages)
                if toolbox.context.finished is not None:
                    return toolbox.context.finished
                reminded = False  # working again: the reminder is for the next stop
                continue
            if response.stop_reason == "pause_turn":  # the server resumes the turn: send no new message
                paused = True
                continue
            if reminded:
                return self._block(context, role, "l'agente ha finito senza consegnare")
            reminded = True
            nudge = {"role": "user", "content": self._reminder(toolbox)}
            transcript.append(nudge)
            messages.append(nudge)

    def _run_tools(
        self, content: list[dict], toolbox: Toolbox, transcript: Transcript, messages: list[dict]
    ) -> None:
        results = []
        for block in content:
            if block.get("type") == "tool_use":
                results.append(toolbox.call(block["id"], block["name"], block.get("input") or {}))
                if toolbox.context.finished is not None:
                    break  # a closed instance's work must not change: later calls in the turn do not run
        reply = {"role": "user", "content": results}
        transcript.append(reply)
        messages.append(reply)

    @staticmethod
    def _reminder(toolbox: Toolbox) -> str:
        """Names only the closing tools this phase has: each phase closes in its own way."""
        available = [name for name in CLOSING if name in toolbox.tools]
        return f"Non hai concluso il ticket. Chiudi con uno di questi strumenti: {', '.join(available)}."

    def _block(self, context: CallContext, role: str, reason: str) -> Outcome:
        status, _ = self.ledger.status(context.ticket_id)
        if status in RUNNABLE:
            with contextlib.suppress(IllegalTransition):
                self.ledger.apply(context.ticket_id, Action.BLOCK, role, reason)
        return Outcome(state=OutcomeState.BLOCKED, note=reason)
