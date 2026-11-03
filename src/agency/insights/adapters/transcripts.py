"""Le trascrizioni delle istanze, in `DataLayout.transcripts`: solo gli strumenti usati e i loro rifiuti.

Il resto della trascrizione, compresi brief, messaggi e risposte, non entra nella proiezione (ADR-0036). Le
righe sono messaggi dell'API Messages: il modello chiede uno strumento con `tool_use`, l'harness risponde con
`tool_result`, e `is_error` dice che lo strumento ha detto no. Una riga tagliata da un motore che sta
scrivendo si conta e si salta.
"""

from __future__ import annotations

import json
from pathlib import Path

from agency.insights.domain import SourceStamp, ToolCallRecord
from agency.insights.ports import TranscriptReading

# Quanto di un rifiuto si tiene. Il motivo sta in testa ("consegna rifiutata: …") o, per l'uscita di un
# programma come craft_run, in fondo: di un testo lungo restano l'inizio e la fine.
REFUSAL_CHARS = 2000
HEAD = 1200
CUT = "\n[…]\n"


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


def _clip(text: str) -> str:
    if len(text) <= REFUSAL_CHARS:
        return text
    return text[:HEAD] + CUT + text[-(REFUSAL_CHARS - HEAD - len(CUT)) :]


def _blocks(message: object) -> list[dict]:
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


class JsonlTranscripts:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _files(self) -> list[Path]:
        return sorted(self.root.glob("*/*.jsonl")) if self.root.is_dir() else []

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
            turn = 0
            asked: dict[
                str, tuple[int, str]
            ] = {}  # tool_use_id -> (turno, strumento), in attesa della risposta
            answers: dict[str, str | None] = {}
            order: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    message = json.loads(line).get("message")
                except (ValueError, AttributeError):
                    unreadable += 1
                    continue
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
