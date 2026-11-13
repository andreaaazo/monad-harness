"""The chain binds what decides money, and the tools' resume records become append-only (ADR-0050).

`operations` gets the `*_no_update` and `*_no_delete` triggers of the other append-only tables. An event may
bind one paid call or one project whole, under `usage` or `project`. One baseline event per paid call, in
`seq` order, then one per project, in name order, binds the row as it is now, outside any ticket's history
(`-`). No row is rewritten.

An applied migration never changes (ADR-0025), so this one carries its own copy of the version-2 digest, of
the canonical JSON and of the columns it binds, instead of importing `agency.ledger.chain` or the models.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from alembic import op
from sqlalchemy import Connection

revision = "0008"
down_revision = "0007"

TRIGGERS = (
    """
CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
BEGIN
    SELECT RAISE(ABORT, 'operations è solo in aggiunta');
END
""",
    """
CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
BEGIN
    SELECT RAISE(ABORT, 'operations è solo in aggiunta');
END
""",
)
GENESIS = "0" * 64
NO_TICKET = "-"
INSERT = (
    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, version, payload_json)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
# Each bound table: its key in the payload, its name, the column it is ordered by, and its columns.
ROWS = (
    (
        "usage",
        "usage",
        "seq",
        (
            "seq",
            "at",
            "project",
            "ticket_id",
            "role",
            "instance",
            "model",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_5m_tokens",
            "cache_write_1h_tokens",
            "cost_usd",
            "stop_reason",
            "request_id",
            "run",
            "phase",
            "effort",
            "duration_ms",
            "ttft_ms",
            "reasoning_tokens",
        ),
    ),
    ("project", "projects", "name", ("name", "budget_usd", "model", "effort")),
)


def _canonical(binding: dict[str, Any]) -> str:
    return json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _bindings(connection: Connection) -> list[dict[str, Any]]:
    """Every paid call, then every project, whole: what each event binds."""
    found: list[dict[str, Any]] = []
    for key, table, order, columns in ROWS:
        for values in connection.exec_driver_sql(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order}"
        ).all():
            found.append({key: dict(zip(columns, values, strict=True))})
    return found


def upgrade() -> None:
    for statement in TRIGGERS:
        op.execute(statement)
    connection = op.get_bind()
    last = connection.exec_driver_sql("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").first()
    prev = last[0] if last else GENESIS
    at = datetime.now(UTC).isoformat(timespec="seconds")  # the format of the ledger's own timestamps
    for binding in _bindings(connection):
        payload_json = _canonical(binding)
        digest = _digest_v2(prev, NO_TICKET, at, "migrate", "baseline", "", payload_json)
        connection.exec_driver_sql(
            INSERT, (NO_TICKET, at, "migrate", "baseline", "", prev, digest, 2, payload_json)
        )
        prev = digest


def downgrade() -> None:
    raise NotImplementedError("the registry does not go back: restore the copy agency migrate made")
