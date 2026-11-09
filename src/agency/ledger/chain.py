"""La catena di hash degli eventi: chi la scrive e chi la verifica usano le stesse regole."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

GENESIS = "0" * 64


def digest(prev: str, ticket_id: str, at: str, actor: str, action: str, note: str) -> str:
    payload = json.dumps([prev, ticket_id, at, actor, action, note], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    """Version 2 also covers the ticket state the event leaves behind (ADR-0047)."""
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def ticket_state(status: str, verdict: str | None, delivered: dict[str, str]) -> str:
    """The canonical JSON of a ticket's mutable state, as a version-2 event binds it (ADR-0047)."""
    state = {"delivered": delivered, "status": status, "verdict": verdict}
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _expected(prev: str, row: Any) -> str | None:
    """The hash `row` must have, by the formula of its version: None for a version no formula knows."""
    if row.version == 1:
        return digest(prev, row.ticket_id, row.at, row.actor, row.action, row.note)
    if row.version == 2:
        return digest_v2(prev, row.ticket_id, row.at, row.actor, row.action, row.note, row.payload_json)
    return None


def intact(rows: Iterable[Any]) -> bool:
    """`rows` sono gli eventi in ordine di `seq`, con i campi della tabella `events`."""
    prev = GENESIS
    for row in rows:
        if row.prev_hash != prev or row.hash != _expected(prev, row):
            return False
        prev = row.hash
    return True
