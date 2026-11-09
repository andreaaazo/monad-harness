"""Events bind the ticket state: verdicts and delivered hashes enter the hash chain (ADR-0047).

A version-2 event carries the status, verdict and delivered hashes its ticket has after it, in
`payload_json`, and its digest covers them. The rows written before stay version 1 and keep their formula.
One baseline event per ticket binds the state `tickets` holds now, at the time of the migration.

An applied migration never changes (ADR-0025), so this one carries its own copy of the version-2 digest and
of the canonical state, instead of importing `agency.ledger.chain`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from alembic import op

revision = "0006"
down_revision = "0005"

STATEMENTS = (
    "ALTER TABLE events ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE events ADD COLUMN payload_json VARCHAR NOT NULL DEFAULT ''",
)
GENESIS = "0" * 64
INSERT = (
    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, version, payload_json)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _state(status: str, verdict: str | None, delivered_json: str) -> str:
    state = {"delivered": json.loads(delivered_json), "status": status, "verdict": verdict}
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)
    connection = op.get_bind()
    last = connection.exec_driver_sql("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").first()
    prev = last[0] if last else GENESIS
    at = datetime.now(UTC).isoformat(timespec="seconds")  # the format of the ledger's own timestamps
    tickets = connection.exec_driver_sql(
        "SELECT id, status, verdict, delivered_json FROM tickets ORDER BY rowid"
    )
    for ticket_id, status, verdict, delivered_json in tickets.all():
        payload_json = _state(status, verdict, delivered_json)
        digest = _digest_v2(prev, ticket_id, at, "migrate", "baseline", "", payload_json)
        connection.exec_driver_sql(
            INSERT, (ticket_id, at, "migrate", "baseline", "", prev, digest, 2, payload_json)
        )
        prev = digest


def downgrade() -> None:
    raise NotImplementedError("the registry does not go back: restore the copy agency migrate made")
