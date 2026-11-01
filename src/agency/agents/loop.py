"""Il loop di un'istanza: un ticket, una sola cronologia in aggiunta, nessuna attesa."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from opentelemetry import trace

from agency.agents import prompts
from agency.agents.transcript import Transcript
from agency.config import Settings
from agency.contracts.ticket import Action, Status, TicketSpec
from agency.gateway import CallContext, ModelGateway, ModelRequest, ModelResponse
from agency.ledger import IllegalTransition, Ledger
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import Sandbox
from agency.tools.surface import Toolbox, ToolContext, tools_for

tracer = trace.get_tracer("agency.agents")
MODE_PROMPTS = {"plan": "director-plan", "select": "director-select", "present": "director-present"}
MAX_TOKENS = 32000
API_MAX_TOKENS = 128000
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


@dataclass(frozen=True)
class Outcome:
    state: str
    note: str = ""

    def to_dict(self) -> dict:
        return {"state": self.state, "note": self.note}


class AgentRunner:
    def __init__(
        self, gateway: ModelGateway, ledger: Ledger, settings: Settings, index: CommandIndex
    ) -> None:
        self.gateway = gateway
        self.ledger = ledger
        self.settings = settings
        self.index = index

    def instance_id(self, ticket_id: str, attempt: int) -> str:
        return f"{ticket_id}-a{attempt}"

    def run(
        self, ticket_id: str, attempt: int = 1, rework_note: str = "", mode: str = "", exploration: int = 0
    ) -> Outcome:
        """`mode` è una fase del direttore sullo stesso ticket: plan, select o present.

        `exploration` è il giro di idee a cui appartiene il lavoro, se è diverso dal tentativo.
        """
        spec = self.ledger.spec(ticket_id)
        project = self.ledger.project_of(ticket_id)
        role = spec.assignee
        instance = f"{self.instance_id(ticket_id, attempt)}{'-' + mode if mode else ''}"
        transcript = Transcript(self.settings.data_dir / "runs" / project / f"{instance}.jsonl")
        finished = transcript.outcome()
        if finished:  # la ripresa non rifà un lavoro già concluso
            return Outcome(finished["state"], finished.get("note", ""))
        work = self.settings.project_dir(project) / "work" / spec.workspace
        work.mkdir(parents=True, exist_ok=True)
        prompt = MODE_PROMPTS.get(mode) or spec.prompt or role
        toolbox = Toolbox(
            ToolContext(
                actor=role,
                project=project,
                ticket_id=ticket_id,
                instance=instance,
                ledger=self.ledger,
                sandbox=Sandbox(work, self.settings.toolchain_dir),
                index=self.index,
                mode=mode,
                round=exploration or attempt,
                settings=self.settings,
            ),
            tools_for(role, spec, mode),
        )
        context = CallContext(project, ticket_id, role, instance)
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attributes(
                {"agency.ticket": ticket_id, "agency.role": role, "agency.instance": instance}
            )
            outcome = self._loop(spec, prompt, context, toolbox, transcript, rework_note)
            span.set_attribute("agency.outcome", outcome.state)
        transcript.finish(outcome.to_dict())
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
        config = prompts.ROLES[role]
        choice = self.ledger.project(context.project)  # modello ed effort li sceglie il cliente
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
            if messages[-1]["role"] == "assistant" and not paused:  # interrotto dopo una risposta
                content = messages[-1]["content"]
                if any(block.get("type") == "tool_use" for block in content):
                    self._run_tools(content, toolbox, transcript, messages)
                    if toolbox.context.finished:
                        return Outcome(*toolbox.context.finished)
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
                limit = API_MAX_TOKENS  # la risposta troncata non entra in cronologia
                continue
            limit = MAX_TOKENS
            assistant = {"role": "assistant", "content": response.content}
            transcript.append(assistant)
            messages.append(assistant)
            if response.stop_reason == "tool_use":
                self._run_tools(response.content, toolbox, transcript, messages)
                if toolbox.context.finished:
                    return Outcome(*toolbox.context.finished)
                reminded = False  # ha ripreso a lavorare: il promemoria vale per la prossima pausa
                continue
            if response.stop_reason == "pause_turn":  # il server riprende da solo: nessun messaggio in più
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
                if toolbox.context.finished:
                    break  # dopo la chiusura il lavoro non cambia più: ciò che segue non si esegue
        reply = {"role": "user", "content": results}
        transcript.append(reply)
        messages.append(reply)

    @staticmethod
    def _reminder(toolbox: Toolbox) -> str:
        """Nomina solo ciò che questa fase può usare: ogni fase si chiude in modo diverso."""
        available = [name for name in CLOSING if name in toolbox.tools]
        return f"Non hai concluso il ticket. Chiudi con uno di questi strumenti: {', '.join(available)}."

    def _block(self, context: CallContext, role: str, reason: str) -> Outcome:
        status, _ = self.ledger.status(context.ticket_id)
        if status in (Status.OPEN, Status.REWORK):
            with contextlib.suppress(IllegalTransition):
                self.ledger.apply(context.ticket_id, Action.BLOCK, role, reason)
        return Outcome("blocked", reason)
