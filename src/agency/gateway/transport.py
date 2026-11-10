"""Trasporti verso il modello. Il gateway non sa se parla con l'API o con una risposta registrata."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from typing import Protocol

import anthropic

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Transport(Protocol):
    """`stream` restituisce il messaggio come dict, più `_request_id` e, se misurato, `_ttft_ms`."""

    def count_tokens(self, params: dict) -> int: ...

    def stream(self, params: dict) -> dict: ...


class AnthropicTransport:
    """L'unica classe che apre una connessione verso l'API."""

    def __init__(
        self,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client or anthropic.Anthropic(api_key=api_key, max_retries=4)
        self.clock = clock

    def count_tokens(self, params: dict) -> int:
        fields = {k: params[k] for k in ("model", "system", "tools", "messages") if k in params}
        return self.client.messages.count_tokens(**fields).input_tokens

    def stream(self, params: dict) -> dict:
        """Il TTFT si conta fino al primo `content_block_delta`, come nelle tracce dell'SDK."""
        started = self.clock()
        first: float | None = None
        with self.client.beta.messages.stream(**params, betas=[FALLBACK_BETA], fallbacks="default") as stream:
            for event in stream:
                if first is None and event.type == "content_block_delta":
                    first = self.clock()
            message = stream.get_final_message()
            request_id = stream.request_id or ""
        data = message.to_dict()
        data["_request_id"] = request_id
        data["_ttft_ms"] = round((first - started) * 1000) if first is not None else None
        return data


class ScriptedTransport:
    """Risposte preparate o registrate: i test non spendono."""

    def __init__(self, responses: Iterable[dict], tokens: int = 1000) -> None:
        self.responses = list(responses)
        self.tokens = tokens
        self.requests: list[dict] = []

    def count_tokens(self, params: dict) -> int:
        return self.tokens

    def stream(self, params: dict) -> dict:
        self.requests.append(json.loads(json.dumps(params)))
        if not self.responses:
            raise AssertionError("risposte registrate esaurite")
        return self.responses.pop(0)
