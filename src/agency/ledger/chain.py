"""The events' hash chain: the code that writes it and the code that verifies it share these rules."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

GENESIS = "0" * 64


def digest(prev: str, ticket_id: str, at: str, actor: str, action: str, note: str) -> str:
    """The version-1 hash: it binds the event and the hash before it, but no ticket state."""
    payload = json.dumps([prev, ticket_id, at, actor, action, note], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    """Version 2 also covers the ticket state the event leaves behind (ADR-0047)."""
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical(binding: dict[str, Any]) -> str:
    """The canonical JSON a version-2 event carries in `payload_json`: sorted keys, no spaces (ADR-0047)."""
    return json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ticket_binding(
    status: str, verdict: str | None, delivered: dict[str, str], spec_json: str, inputs_json: str
) -> dict[str, Any]:
    """What a version-2 event binds of its ticket: the state the event leaves (ADR-0047), and the sha256 of
    the contract and of the opening hashes as stored, which no code changes after `open` (ADR-0049)."""
    return {
        "delivered": delivered,
        "inputs_sha256": text_sha256(inputs_json),
        "spec_sha256": text_sha256(spec_json),
        "status": status,
        "verdict": verdict,
    }


def _expected(prev: str, row: Any) -> str | None:
    """The hash `row` must have, by the formula of its version: None for a version no formula knows."""
    if row.version == 1:
        return digest(prev, row.ticket_id, row.at, row.actor, row.action, row.note)
    if row.version == 2:
        return digest_v2(prev, row.ticket_id, row.at, row.actor, row.action, row.note, row.payload_json)
    return None


def intact(rows: Iterable[Any]) -> bool:
    """True if each event links to the one before and has its version's hash. `rows` are the events in
    `seq` order, with the fields of the `events` table."""
    prev = GENESIS
    for row in rows:
        if row.prev_hash != prev or row.hash != _expected(prev, row):
            return False
        prev = row.hash
    return True
