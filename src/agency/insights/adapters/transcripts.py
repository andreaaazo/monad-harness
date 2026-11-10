"""The instances' transcripts, at the `DataLayout` paths: read-only.

For the projection only the tools used and their refusals are read (ADR-0036). For the replay view a whole
instance is read when it is opened, and nothing is copied from it (ADR-0038). The lines are Messages API
messages: the model asks for a tool with `tool_use`, the harness answers with `tool_result`, and `is_error`
says the tool said no. A line cut short by an engine that is still writing is counted and skipped.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterator
from pathlib import Path

from agency.contracts import phase
from agency.contracts.layout import DataLayout
from agency.contracts.project import parse_project_name
from agency.insights.domain import (
    AssistantTurn,
    ImageRef,
    SourceStamp,
    ToolCallRecord,
    ToolExchange,
    TranscriptImage,
    TranscriptRecord,
)
from agency.insights.ports import TranscriptReading

# How much of a refusal the projection keeps. The reason is at the start ("consegna rifiutata: …") or, in
# the output of a program such as craft_run, at the end: a long text keeps its start and its end.
REFUSAL_CHARS = 2000
HEAD = 1200
# In the replay view a result reads almost whole: only a program's very long output is shortened.
RESULT_CHARS = 20000
RESULT_HEAD = 12000
CUT = "\n[…]\n"
# The images the dashboard serves: no SVG, which can hold scripts.
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "\n".join(parts)
    return ""


def _clip(text: str, limit: int = REFUSAL_CHARS, head: int = HEAD) -> str:
    if len(text) <= limit:
        return text
    return text[:head] + CUT + text[-(limit - head - len(CUT)) :]


def _blocks(message: object) -> list[dict]:
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _pictures(content: object) -> Iterator[dict]:
    """A result's images, in order: their position numbers them across the whole transcript."""
    if isinstance(content, list):
        yield from (part for part in content if isinstance(part, dict) and part.get("type") == "image")


class JsonlTranscripts:
    """The `TranscriptReader` on the JSONL files under `DataLayout.transcripts`."""

    def __init__(self, layout: DataLayout) -> None:
        self.layout = layout
        self.root = layout.transcripts

    def _files(self) -> list[Path]:
        return sorted(self.root.glob("*/*.jsonl")) if self.root.is_dir() else []

    def _path(self, project: str, instance: str) -> Path | None:
        """An instance's file: only for an instance name, and only inside the transcripts folder."""
        if phase.INSTANCE.fullmatch(instance) is None:
            return None
        try:
            name = parse_project_name(project)
        except ValueError:
            return None
        path = self.layout.transcript(name, instance).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            return None
        return path

    @staticmethod
    def _entries(path: Path) -> tuple[list[dict], int]:
        entries, unreadable = [], 0
        for line in path.read_bytes().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line.decode("utf-8"))
            except ValueError:  # UnicodeDecodeError is a ValueError: a torn line is counted, not fatal
                unreadable += 1
                continue
            if isinstance(entry, dict):
                entries.append(entry)
            else:
                unreadable += 1
        return entries, unreadable

    def stamp(self) -> list[SourceStamp]:
        stamps = []
        for path in self._files():
            status = path.stat()
            name = f"{self.root.name}/{path.parent.name}/{path.name}"
            stamps.append(SourceStamp(name=name, size=status.st_size, modified_ns=status.st_mtime_ns))
        return stamps

    def read(self) -> TranscriptReading:
        calls: list[ToolCallRecord] = []
        unreadable = 0
        for path in self._files():
            project, instance = path.parent.name, path.stem
            entries, broken = self._entries(path)
            unreadable += broken
            turn = 0
            # tool_use_id -> (turn, tool), until its answer arrives
            asked: dict[str, tuple[int, str]] = {}
            answers: dict[str, str | None] = {}
            order: list[str] = []
            for entry in entries:
                message = entry.get("message")
                if isinstance(message, dict) and message.get("role") == "assistant":
                    turn += 1
                for block in _blocks(message):
                    if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                        asked[block["id"]] = (turn, str(block.get("name", "")))
                        order.append(block["id"])
                    elif block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
                        refused = block.get("is_error") is True
                        answers[block["tool_use_id"]] = (
                            _clip(_text(block.get("content"))) if refused else None
                        )
            for use in order:
                at_turn, tool = asked[use]
                calls.append(
                    ToolCallRecord(
                        seq=len(calls) + 1,
                        project=project,
                        instance=instance,
                        turn=at_turn,
                        tool=tool,
                        refusal=answers.get(use),
                    )
                )
        return TranscriptReading(calls=calls, unreadable=unreadable)

    def transcript(self, project: str, instance: str) -> TranscriptRecord | None:
        path = self._path(project, instance)
        if path is None:
            return None
        entries, unreadable = self._entries(path)
        task: list[str] = []
        turns: list[dict] = []
        tools: dict[str, dict] = {}  # tool_use_id -> the exchange, until its answer arrives
        outcome: dict = {}
        images = 0
        for entry in entries:
            if isinstance(entry.get("outcome"), dict):
                outcome = entry["outcome"]
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            if message.get("role") == "assistant":
                current: dict = {
                    "request_id": entry.get("request_id")
                    if isinstance(entry.get("request_id"), str)
                    else None,
                    "thinking": [],
                    "hidden_thinking": 0,
                    "text": [],
                    "tools": [],
                    "notes": [],
                }
                for block in _blocks(message):
                    kind = block.get("type")
                    if kind == "thinking" and isinstance(block.get("thinking"), str):
                        current["thinking"].append(block["thinking"])
                    elif kind == "redacted_thinking":
                        current["hidden_thinking"] += 1
                    elif kind == "text" and isinstance(block.get("text"), str):
                        current["text"].append(block["text"])
                    elif kind == "tool_use" and isinstance(block.get("id"), str):
                        exchange = {
                            "name": str(block.get("name", "")),
                            "input": json.dumps(block.get("input", {}), ensure_ascii=False, indent=2),
                            "answered": False,
                            "refused": False,
                            "result": "",
                            "images": [],
                        }
                        tools[block["id"]] = exchange
                        current["tools"].append(exchange)
                turns.append(current)
                continue
            notes = task if not turns else turns[-1]["notes"]
            if isinstance(message.get("content"), str):
                notes.append(message["content"])
            for block in _blocks(message):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    notes.append(block["text"])
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in tools:
                    exchange = tools[block["tool_use_id"]]
                    exchange["answered"] = True
                    exchange["refused"] = block.get("is_error") is True
                    exchange["result"] = _clip(_text(block.get("content")), RESULT_CHARS, RESULT_HEAD)
                    for picture in _pictures(block.get("content")):
                        source = picture.get("source")
                        kind = source.get("media_type", "") if isinstance(source, dict) else ""
                        exchange["images"].append(
                            ImageRef(index=images, media_type=str(kind), servable=kind in IMAGE_TYPES)
                        )
                        images += 1
        return TranscriptRecord(
            project=project,
            instance=instance,
            task="\n\n".join(task),
            turns=[
                AssistantTurn(
                    request_id=item["request_id"],
                    thinking=item["thinking"],
                    hidden_thinking=item["hidden_thinking"],
                    text=item["text"],
                    tools=[ToolExchange.model_validate(tool) for tool in item["tools"]],
                    notes=item["notes"],
                )
                for item in turns
            ],
            outcome_state=str(outcome["state"]) if "state" in outcome else None,
            outcome_note=str(outcome.get("note", "")),
            images=images,
            unreadable=unreadable,
        )

    def image(self, project: str, instance: str, index: int) -> TranscriptImage | None:
        path = self._path(project, instance)
        if path is None:
            return None
        seen = 0
        for entry in self._entries(path)[0]:
            for block in _blocks(entry.get("message")):
                if block.get("type") != "tool_result":
                    continue
                for picture in _pictures(block.get("content")):
                    if seen == index:
                        return self._decode(picture)
                    seen += 1
        return None

    @staticmethod
    def _decode(picture: dict) -> TranscriptImage | None:
        source = picture.get("source")
        if not isinstance(source, dict) or source.get("type") != "base64":
            return None
        media_type, data = source.get("media_type"), source.get("data")
        if media_type not in IMAGE_TYPES or not isinstance(data, str):
            return None
        try:
            return TranscriptImage(media_type=media_type, data=base64.b64decode(data, validate=True))
        except (binascii.Error, ValueError):
            return None
