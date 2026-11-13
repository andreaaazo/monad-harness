"""The model gateway: the one place that calls the API, with budget, caching and usage."""

# The API error the CLI catches, re-exported so that no package but the gateway imports anthropic (ADR-0021).
from anthropic import APIError

from agency.gateway.client import BudgetExceeded, CallContext, ModelGateway, ModelRequest, ModelResponse
from agency.gateway.recording import RecordingTransport, request_key
from agency.gateway.transport import AnthropicTransport, Transport

__all__ = [
    "APIError",
    "AnthropicTransport",
    "BudgetExceeded",
    "CallContext",
    "ModelGateway",
    "ModelRequest",
    "ModelResponse",
    "RecordingTransport",
    "Transport",
    "request_key",
]
