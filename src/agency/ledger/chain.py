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


def intact(rows: Iterable[Any]) -> bool:
    """`rows` sono gli eventi in ordine di `seq`, con i campi della tabella `events`."""
    prev = GENESIS
    for row in rows:
        expected = digest(prev, row.ticket_id, row.at, row.actor, row.action, row.note)
        if row.prev_hash != prev or row.hash != expected:
            return False
        prev = row.hash
    return True
