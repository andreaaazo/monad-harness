"""Gateway del modello: autorizza la spesa, compone la richiesta, registra il consumo."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from opentelemetry import trace

from agency.config import Settings
from agency.gateway.pricing import cost_usd, price_of
from agency.gateway.transport import Transport
from agency.ledger import Ledger
from agency.ledger.models import UsageRow
from agency.ledger.store import now

tracer = trace.get_tracer("agency.gateway")
EXPECTED_OUTPUT_TOKENS = 4000
IMAGE_TOKENS = 2500
MAX_MALFORMED_RETRIES = 2


class BudgetExceeded(Exception):
    """La chiamata supererebbe un tetto: il lavoro si ferma in uno stato ripartibile."""


@dataclass(frozen=True)
class CallContext:
    project: str
    ticket_id: str
    role: str
    instance: str
    phase: str  # il prompt della fase: un ruolo ne ha più d'una, come il direttore


@dataclass
class ModelRequest:
    model: str
    effort: str
    system: list[dict]
    messages: list[dict]
    tools: list[dict] = field(default_factory=list)
    max_tokens: int = 32000


@dataclass
class ModelResponse:
    content: list[dict]
    stop_reason: str
    stop_details: dict | None
    usage: dict
    model: str
    cost_usd: float
    request_id: str

    @property
    def context_tokens(self) -> int:
        return (
            (self.usage.get("input_tokens", 0) or 0)
            + (self.usage.get("cache_read_input_tokens", 0) or 0)
            + (self.usage.get("cache_creation_input_tokens", 0) or 0)
        )


def _fresh_tokens(message: dict) -> int:
    """Stima prudente dei token nuovi: un'immagine non si conta dai caratteri del base64."""
    content = message.get("content")
    if isinstance(content, str):
        return len(content) // 3
    total = 0
    for block in content or []:
        if block.get("type") == "tool_result":
            total += _fresh_tokens({"content": block.get("content")})
        elif block.get("type") == "image":
            total += IMAGE_TOKENS
        else:
            total += len(str(block.get("text", ""))) // 3
    return total


class ModelGateway:
    def __init__(
        self,
        transport: Transport,
        ledger: Ledger,
        settings: Settings,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport
        self.ledger = ledger
        self.settings = settings
        self.clock = clock
        self.run: int | None = None

    def belongs_to(self, run: int) -> None:
        """Le chiamate da qui in poi appartengono a questa esecuzione, registrata prima del grafo."""
        self.run = run

    def _params(self, request: ModelRequest) -> dict:
        params: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": request.messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": request.effort},
            # Breakpoint esplicito sul sistema, automatico sulla coda della conversazione.
            "cache_control": {"type": "ephemeral"},
        }
        if request.tools:
            params["tools"] = request.tools
        return params

    def estimate_usd(self, request: ModelRequest, previous: ModelResponse | None) -> float:
        price = price_of(request.model)
        if previous is None:
            tokens = self.transport.count_tokens(self._params(request))
            input_cost = tokens * price.cache_write_5m
        else:
            fresh = _fresh_tokens(request.messages[-1])
            input_cost = previous.context_tokens * price.cache_read + fresh * price.cache_write_5m
        return (input_cost + EXPECTED_OUTPUT_TOKENS * price.output) / 1_000_000

    def project_limit(self, project: str) -> float:
        """Il tetto che il cliente ha dichiarato all'avvio: un progetto senza non spende (ADR-0043)."""
        row = self.ledger.project(project)
        if row is None:
            raise BudgetExceeded(f"{project} non ha un tetto dichiarato: si dichiara con agency run --budget")
        return row.budget_usd

    def authorize(self, context: CallContext, limit: float, estimate: float) -> None:
        """L'unico vincolo è il budget scelto dal cliente: nessun altro tetto ferma il lavoro."""
        spent = self.ledger.spent(context.project)
        if spent + estimate > limit:
            raise BudgetExceeded(f"{spent:.2f} $ spesi su {limit:.2f} $")

    def call(
        self, context: CallContext, request: ModelRequest, previous: ModelResponse | None = None
    ) -> ModelResponse:
        limit = self.project_limit(context.project)  # prima della stima: senza tetto non esce nulla
        self.authorize(context, limit, self.estimate_usd(request, previous))
        params = self._params(request)
        with tracer.start_as_current_span("model.call") as span:
            span.set_attributes(
                {
                    "agency.project": context.project,
                    "agency.ticket": context.ticket_id,
                    "agency.role": context.role,
                    "gen_ai.request.model": request.model,
                }
            )
            started = self.clock()
            data = self._stream(params)
            duration_ms = round((self.clock() - started) * 1000)
            response = self._record(context, request, data, duration_ms)
            span.set_attribute("agency.cost_usd", response.cost_usd)
        return response

    def _stream(self, params: dict) -> dict:
        for attempt in range(MAX_MALFORMED_RETRIES + 1):
            try:
                return self.transport.stream(params)
            except ValueError:  # JSON degli strumenti illeggibile nello stream: si ripete la richiesta.
                if attempt == MAX_MALFORMED_RETRIES:
                    raise
        raise AssertionError("non raggiungibile")

    def _record(
        self, context: CallContext, request: ModelRequest, data: dict, duration_ms: int
    ) -> ModelResponse:
        usage = data.get("usage") or {}
        details = usage.get("output_tokens_details") or {}
        model = data.get("model") or ""
        cost = cost_usd(model, usage)
        breakdown = usage.get("cache_creation") or {}
        self.ledger.record_usage(
            UsageRow(
                at=now(),
                project=context.project,
                ticket_id=context.ticket_id,
                role=context.role,
                instance=context.instance,
                model=model,
                input_tokens=usage.get("input_tokens", 0) or 0,
                output_tokens=usage.get("output_tokens", 0) or 0,
                cache_read_tokens=usage.get("cache_read_input_tokens", 0) or 0,
                cache_write_5m_tokens=breakdown.get(
                    "ephemeral_5m_input_tokens", usage.get("cache_creation_input_tokens", 0) or 0
                ),
                cache_write_1h_tokens=breakdown.get("ephemeral_1h_input_tokens", 0) or 0,
                cost_usd=cost,
                stop_reason=data.get("stop_reason") or "",
                request_id=data.get("_request_id", ""),
                run=self.run,
                phase=context.phase,
                effort=request.effort,
                duration_ms=duration_ms,
                ttft_ms=data.get("_ttft_ms"),
                reasoning_tokens=details.get("thinking_tokens"),
            )
        )
        return ModelResponse(
            content=data.get("content") or [],
            stop_reason=data.get("stop_reason") or "",
            stop_details=data.get("stop_details"),
            usage=usage,
            model=model,
            cost_usd=cost,
            request_id=data.get("_request_id", ""),
        )
