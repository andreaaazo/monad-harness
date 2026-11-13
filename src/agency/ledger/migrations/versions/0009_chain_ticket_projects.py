"""The chain binds each ticket's project (ADR-0053).

A version-2 event of a ticket also binds the ticket's `project`: it decides whose work folder the ticket's
agents write and whose budget pays its calls, and no code changes it after `open`. One baseline event per
ticket, in creation order, binds the state, the contract and the project `tickets` holds now. The schema
does not change, and no row is rewritten.

An applied migration never changes (ADR-0025), so this one carries its own copy of the version-2 digest, of
the canonical JSON and of the ticket binding, instead of importing `agency.ledger.chain`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from alembic import op

revision = "0009"
down_revision = "0008"

GENESIS = "0" * 64
INSERT = (
    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, version, payload_json)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
TICKETS = (
    "SELECT id, project, status, verdict, delivered_json, spec_json, inputs_json FROM tickets ORDER BY rowid"
)


def _canonical(binding: dict[str, Any]) -> str:
    return json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def upgrade() -> None:
    connection = op.get_bind()
    last = connection.exec_driver_sql("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").first()
    prev = last[0] if last else GENESIS
    at = datetime.now(UTC).isoformat(timespec="seconds")  # the format of the ledger's own timestamps
    tickets = connection.exec_driver_sql(TICKETS).all()
    for ticket_id, project, status, verdict, delivered_json, spec_json, inputs_json in tickets:
        payload_json = _canonical(
            {
                "delivered": json.loads(delivered_json),
                "inputs_sha256": _sha256(inputs_json),
                "project": project,
                "spec_sha256": _sha256(spec_json),
                "status": status,
                "verdict": verdict,
            }
        )
        digest = _digest_v2(prev, ticket_id, at, "migrate", "baseline", "", payload_json)
        connection.exec_driver_sql(
            INSERT, (ticket_id, at, "migrate", "baseline", "", prev, digest, 2, payload_json)
        )
        prev = digest


def downgrade() -> None:
    raise NotImplementedError("the registry does not go back: restore the copy agency migrate made")
