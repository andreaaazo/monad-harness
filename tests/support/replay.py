"""Replay of a recorded run: each request gets the answer recorded for it, whatever the order (ADR-0048).

Nothing under `src/` imports this module, so no production path can answer from a recording.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path

from agency.gateway import request_key

SHOWN = 80  # characters of the last message a miss quotes


class MissingRecording(AssertionError):
    """A request the recording does not hold: the replayed run left the recorded path at this turn."""

    def __init__(self, key: str, summary: str) -> None:
        super().__init__(f"no recorded answer for {summary} (key {key})")
        self.key = key
        self.summary = summary


def _text(content: object) -> str:
    """The readable text of a message's content: plain text, text blocks and tool results."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content if isinstance(content, list) else []:
        if block.get("type") == "tool_result":
            parts.append(_text(block.get("content")))
        elif "text" in block:
            parts.append(str(block["text"]))
    return " ".join(parts)


def summarize(kind: str, params: dict) -> str:
    """The kind of call, the model, how many messages, and how the last one starts."""
    messages = params.get("messages") or []
    start = " ".join(_text(messages[-1].get("content")).split())[:SHOWN] if messages else ""
    return f"{kind} to {params.get('model')} with {len(messages)} messages, the last starting {start!r}"


class ReplayTransport:
    """Answers from a cassette by `(kind, request key)`. Repeated requests get theirs in recorded order."""

    def __init__(self, path: Path) -> None:
        self._answers: dict[tuple[str, str], deque[int | dict]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            self._answers.setdefault((record["kind"], record["key"]), deque()).append(record["response"])
        self._lock = threading.Lock()  # explorers replay in parallel, as they recorded

    def _next(self, kind: str, params: dict) -> int | dict:
        key = request_key(params)
        with self._lock:
            answers = self._answers.get((kind, key))
            if not answers:
                raise MissingRecording(key, summarize(kind, params))
            return answers.popleft()

    def count_tokens(self, params: dict) -> int:
        tokens = self._next("count_tokens", params)
        assert isinstance(tokens, int)
        return tokens

    def stream(self, params: dict) -> dict:
        response = self._next("stream", params)
        assert isinstance(response, dict)
        return response

    def left(self) -> int:
        """Recorded answers no request has asked for yet: 0 once a replay made every recorded call."""
        with self._lock:
            return sum(len(answers) for answers in self._answers.values())
