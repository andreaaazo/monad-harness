"""A model transport for tests: it answers from a script, so no test calls the API."""

from __future__ import annotations

import json
from collections.abc import Iterable


class ScriptedTransport:
    """Prepared or recorded answers, so tests spend nothing."""

    def __init__(self, responses: Iterable[dict], tokens: int = 1000) -> None:
        self.responses = list(responses)
        self.tokens = tokens
        self.requests: list[dict] = []

    def count_tokens(self, params: dict) -> int:
        return self.tokens

    def stream(self, params: dict) -> dict:
        self.requests.append(json.loads(json.dumps(params)))
        if not self.responses:
            raise AssertionError("no recorded responses left")
        return self.responses.pop(0)
