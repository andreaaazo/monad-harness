"""Gateway del modello: unico punto di chiamata all'API, con budget, cache e consumi."""

from agency.gateway.client import BudgetExceeded, CallContext, ModelGateway, ModelRequest, ModelResponse
from agency.gateway.recording import RecordingTransport, request_key
from agency.gateway.transport import AnthropicTransport, ScriptedTransport, Transport

__all__ = [
    "AnthropicTransport",
    "BudgetExceeded",
    "CallContext",
    "ModelGateway",
    "ModelRequest",
    "ModelResponse",
    "RecordingTransport",
    "ScriptedTransport",
    "Transport",
    "request_key",
]
