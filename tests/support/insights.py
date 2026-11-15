"""What more than one insights test file uses: the records, the registry built for a test and the
projection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agency.contracts.ledger import UsageEntry
from agency.insights.domain import (
    Call,
    EventRecord,
    Lifecycle,
    SourceStamp,
    TicketRecord,
    UsageRecord,
    project_calls,
)
from agency.insights.ports import LedgerSnapshot
from agency.ledger import Ledger


def usage(**extra: object) -> UsageRecord:
    base: dict[str, object] = {
        "seq": 1,
        "at": "2026-11-02T10:00:00+00:00",
        "project": "merlo3",
        "ticket_id": "T-0001",
        "role": "design-director",
        "instance": "T-0001-a1-plan",
        "model": "claude-opus-5-5",
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_usd": 0.01,
        "stop_reason": "tool_use",
        "request_id": "req_1",
        "run": None,
        "phase": None,
        "effort": None,
        "duration_ms": None,
        "ttft_ms": None,
        "reasoning_tokens": None,
    }
    return UsageRecord.model_validate(base | extra)


def ticket(id_: str, type_: str, assignee: str, prompt: str = "") -> TicketRecord:
    return TicketRecord(
        id=id_,
        project="merlo3",
        type=type_,
        assignee=assignee,
        prompt=prompt,
        title=f"Ticket {id_}",
        status="accepted",
        verdict=None,
        created_at="2026-11-02T09:00:00+00:00",
    )


TICKETS = {
    "T-0001": ticket("T-0001", "consegna", "design-director"),
    "T-0002": ticket("T-0002", "schizzo", "direction-a", "explorer"),
    "T-0009": ticket("T-0009", "revisione", "critic"),
}


# The traces


def span(name: str, request_id: str, **attributes: object) -> str:
    record = {
        "name": name,
        "start": 1_000_000_000,
        "end": 1_000_000_000 + 8_200_000_000,
        "trace": "abc",
        "attributes": {"anthropic.request.id": request_id} | attributes,
    }
    return json.dumps(record)


# The transcripts: from each, only the tools used and their refusals


def turn(*blocks: dict) -> dict:
    return {"role": "assistant", "content": list(blocks)}


def results(*blocks: dict) -> dict:
    return {"role": "user", "content": list(blocks)}


def use(id_: str, name: str) -> dict:
    return {"type": "tool_use", "id": id_, "name": name, "input": {"path": "segno.svg"}}


def answer(id_: str, text: str, *, error: bool = False) -> dict:
    block: dict[str, object] = {"type": "tool_result", "tool_use_id": id_, "content": text}
    return block | {"is_error": True} if error else block


# The registry, read-only


def filled_registry(path: Path) -> Ledger:
    ledger = Ledger(path)
    ledger.record_usage(
        UsageEntry(
            at="2026-11-02T10:00:00+00:00",
            project="merlo4",
            ticket_id="T-0001",
            role="design-director",
            instance="T-0001-a1-plan",
            model="claude-opus-5-5",
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.01,
            stop_reason="tool_use",
            request_id="req_1",
            phase="director-plan",
            effort="high",
            duration_ms=4100,
        )
    )
    return ledger


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeRegistry:
    def __init__(self, revision: str | None) -> None:
        self._revision = revision

    def stamp(self) -> list[SourceStamp]:
        return [SourceStamp(name="ledger.sqlite", size=1, modified_ns=1)]

    def revision(self) -> str | None:
        return self._revision

    def read(self) -> LedgerSnapshot:
        calls = [usage(), usage(seq=2, request_id="req_2", phase="director-plan", duration_ms=10)]
        return LedgerSnapshot(
            usage=calls,
            tickets=TICKETS,
            projects=[],
            gates=[],
            concepts=[],
            judgments=[],
            events=[],
            checks=[],
            runs=[],
        )


# The projection


def call(seq: int, project: str = "merlo3") -> Call:
    (projected,) = project_calls([usage(seq=seq, project=project, request_id=f"req_{seq}")], TICKETS, {})
    return projected


def event(seq: int, project: str, action: Lifecycle) -> EventRecord:
    return EventRecord(
        seq=seq,
        at=f"2026-11-02T10:0{seq}:00+00:00",
        project=project,
        ticket_id="T-0002",
        actor="x",
        action=action,
        reason="perché" if action is Lifecycle.BLOCK else None,
    )
