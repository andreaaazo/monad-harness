"""Trasporti verso il modello. Il gateway non sa se parla con l'API o con una risposta registrata."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import anthropic

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Transport(Protocol):
    def count_tokens(self, params: dict) -> int: ...

    def stream(self, params: dict) -> dict: ...


class AnthropicTransport:
    """L'unica classe che apre una connessione verso l'API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=4)

    def count_tokens(self, params: dict) -> int:
        fields = {k: params[k] for k in ("model", "system", "tools", "messages") if k in params}
        return self.client.messages.count_tokens(**fields).input_tokens

    def stream(self, params: dict) -> dict:
        with self.client.beta.messages.stream(**params, betas=[FALLBACK_BETA], fallbacks="default") as stream:
            message = stream.get_final_message()
            request_id = stream.request_id or ""
        data = message.to_dict()
        data["_request_id"] = request_id
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

    @classmethod
    def from_cassette(cls, path: Path) -> ScriptedTransport:
        lines = path.read_text(encoding="utf-8").splitlines()
        return cls(json.loads(line)["response"] for line in lines if line.strip())


class RecordingTransport:
    """Avvolge un trasporto reale e salva ogni scambio, per ripeterlo poi nei test."""

    def __init__(self, inner: Transport, path: Path) -> None:
        self.inner = inner
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def count_tokens(self, params: dict) -> int:
        return self.inner.count_tokens(params)

    def stream(self, params: dict) -> dict:
        response = self.inner.stream(params)
        record = {"model": params.get("model"), "response": response}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return response
