"""The model gateway: it authorizes the spend, builds the request, and records the usage."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from opentelemetry import trace

from agency.config import Settings
from agency.contracts.clock import now
from agency.contracts.ledger import UsageEntry
from agency.gateway.pricing import call_cost_usd, price_of
from agency.gateway.transport import Transport
from agency.ledger import Ledger

tracer = trace.get_tracer("agency.gateway")
EXPECTED_OUTPUT_TOKENS = 4000
IMAGE_TOKENS = 2500
MAX_MALFORMED_RETRIES = 2


class BudgetExceeded(Exception):
    """The call would go over the project's cap, or there is no cap: the work stops where it can resume."""


@dataclass(frozen=True)
class CallContext:
    """Whom a call works for: it fills the usage row and the trace span."""

    project: str
    ticket_id: str
    role: str
    instance: str
    phase: str  # the phase's prompt: a role can have more than one, like the director


@dataclass
class ModelRequest:
    """One Messages API request, before the gateway adds adaptive thinking and automatic caching."""

    model: str
    effort: str
    system: list[dict]
    messages: list[dict]
    tools: list[dict] = field(default_factory=list)
    max_tokens: int = 32000


@dataclass
class ModelResponse:
    """The final message, its usage and its cost. Read `stop_reason` before `content`."""

    content: list[dict]
    stop_reason: str
    stop_details: dict | None
    usage: dict
    model: str
    cost_usd: float
    request_id: str

    @property
    def context_tokens(self) -> int:
        """The whole prompt: uncached input plus cache reads and writes."""
        return (
            (self.usage.get("input_tokens", 0) or 0)
            + (self.usage.get("cache_read_input_tokens", 0) or 0)
            + (self.usage.get("cache_creation_input_tokens", 0) or 0)
        )


def _fresh_tokens(message: dict) -> int:
    """A generous estimate of the new tokens: an image is not counted by its base64 characters."""
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
    """The one way to call the model: each attempt is authorized against the budget and recorded if billed."""

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
        self._lock = threading.Lock()
        self._reserved: dict[str, float] = {}  # per project: the estimates of calls not recorded yet

    def belongs_to(self, run: int) -> None:
        """The calls from here on belong to this run, which is recorded before the graph starts."""
        self.run = run

    def _params(self, request: ModelRequest) -> dict:
        params: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": request.messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": request.effort},
            # An explicit breakpoint on the system prompt, an automatic one on the tail of the conversation.
            "cache_control": {"type": "ephemeral"},
        }
        if request.tools:
            params["tools"] = request.tools
        return params

    def estimate_usd(self, request: ModelRequest, previous: ModelResponse | None) -> float:
        """The first call is counted by the API; a later one reads the previous context from the cache and
        writes the new message to it. Output is assumed at `EXPECTED_OUTPUT_TOKENS`."""
        price = price_of(request.model)
        if previous is None:
            tokens = self.transport.count_tokens(self._params(request))
            input_cost = tokens * price.cache_write_5m
        else:
            fresh = _fresh_tokens(request.messages[-1])
            input_cost = previous.context_tokens * price.cache_read + fresh * price.cache_write_5m
        return (input_cost + EXPECTED_OUTPUT_TOKENS * price.output) / 1_000_000

    def project_limit(self, project: str) -> float:
        """The cap the client declared at the start: a project without one spends nothing (ADR-0043)."""
        row = self.ledger.project(project)
        if row is None:
            raise BudgetExceeded(f"{project} non ha un tetto dichiarato: si dichiara con agency run --budget")
        return row.budget_usd

    def authorize(self, context: CallContext, limit: float, estimate: float) -> None:
        """Reserves the estimate against the client's budget, the only limit: no other cap stops the work."""
        with self._lock:  # check and reserve in one step: parallel calls cannot share one remaining budget
            spent = self.ledger.spent(context.project)
            reserved = self._reserved.get(context.project, 0.0)
            if spent + reserved + estimate > limit:
                raise BudgetExceeded(f"{spent:.2f} $ spesi su {limit:.2f} $")
            self._reserved[context.project] = reserved + estimate

    def _release(self, project: str, estimate: float) -> None:
        with self._lock:
            self._reserved[project] -= estimate

    def call(
        self, context: CallContext, request: ModelRequest, previous: ModelResponse | None = None
    ) -> ModelResponse:
        limit = self.project_limit(context.project)  # before the estimate: with no cap, nothing goes out
        estimate = self.estimate_usd(request, previous)
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
            for attempt in range(MAX_MALFORMED_RETRIES + 1):
                # Every attempt is billed by the API, so each one is authorized and recorded on its own.
                self.authorize(context, limit, estimate)
                try:  # after a record the spend holds the cost; on an unrecorded error nothing was spent
                    started = self.clock()
                    try:
                        data = self.transport.stream(params)
                    except ValueError:  # the tool JSON was unreadable: send the request again
                        duration_ms = round((self.clock() - started) * 1000)
                        self._record_malformed(context, request, estimate, duration_ms)
                        if attempt == MAX_MALFORMED_RETRIES:
                            raise
                        continue
                    duration_ms = round((self.clock() - started) * 1000)
                    response = self._record(context, request, data, duration_ms)
                    span.set_attribute("agency.cost_usd", response.cost_usd)
                    return response
                finally:
                    self._release(context.project, estimate)
        raise AssertionError("unreachable")

    def _record_malformed(
        self, context: CallContext, request: ModelRequest, estimate: float, duration_ms: int
    ) -> None:
        """A stream that died on unreadable tool JSON was billed but reported no usage: use the estimate."""
        self.ledger.record_usage(
            UsageEntry(
                at=now(),
                project=context.project,
                ticket_id=context.ticket_id,
                role=context.role,
                instance=context.instance,
                model=request.model,
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=0,
                cache_write_5m_tokens=0,
                cache_write_1h_tokens=0,
                cost_usd=estimate,
                stop_reason="malformed_stream",
                request_id="",
                run=self.run,
                phase=context.phase,
                effort=request.effort,
                duration_ms=duration_ms,
                ttft_ms=None,
                reasoning_tokens=None,
            )
        )

    def _record(
        self, context: CallContext, request: ModelRequest, data: dict, duration_ms: int
    ) -> ModelResponse:
        usage = data.get("usage") or {}
        details = usage.get("output_tokens_details") or {}
        model = data.get("model") or ""
        cost = call_cost_usd(model, usage, request.model)
        breakdown = usage.get("cache_creation") or {}
        self.ledger.record_usage(
            UsageEntry(
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
