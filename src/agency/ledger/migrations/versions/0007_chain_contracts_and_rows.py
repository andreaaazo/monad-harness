"""The chain binds what decides a delivery: ticket contracts, ideas, gates and proofs (ADR-0049).

A version-2 event of a ticket also binds the sha256 of the ticket's `spec_json` and `inputs_json`, and an
event may bind one idea, gate or proof whole, under `concept`, `gate` or `evidence`. One baseline event per
ticket binds the state and the contract `tickets` holds now; then one per idea, gate and proof binds the row
as it is now, outside any ticket's history (`-`). The schema does not change.

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

revision = "0007"
down_revision = "0006"

GENESIS = "0" * 64
NO_TICKET = "-"
INSERT = (
    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, version, payload_json)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
TICKETS = "SELECT id, status, verdict, delivered_json, spec_json, inputs_json FROM tickets ORDER BY rowid"
# Each bound table: its key in the payload, its name and its columns. SQLite stores `approved` as 0 or 1, and
# the models read it as a boolean.
ROWS = (
    (
        "concept",
        "concepts",
        (
            "seq",
            "project",
            "round",
            "letter",
            "lever",
            "anon",
            "card_json",
            "idea_ticket",
            "sketch_ticket",
            "sketch_file",
            "status",
        ),
    ),
    ("gate", "gates", ("seq", "at", "project", "gate", "approved", "choice", "text", "files_json")),
    (
        "evidence",
        "evidence",
        (
            "seq",
            "at",
            "project",
            "file",
            "sha256",
            "check_name",
            "result",
            "signer",
            "ticket_id",
            "proof",
            "note",
            "inputs_json",
        ),
    ),
)
BOOLEANS = frozenset({"approved"})


def _canonical(binding: dict[str, Any]) -> str:
    return json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _digest_v2(
    prev: str, ticket_id: str, at: str, actor: str, action: str, note: str, payload_json: str
) -> str:
    payload = json.dumps([prev, ticket_id, at, actor, action, note, payload_json], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _bindings(connection: Connection) -> list[tuple[str, dict[str, Any]]]:
    """Every ticket with its state and contract, then every idea, gate and proof whole: what each event
    binds."""
    found: list[tuple[str, dict[str, Any]]] = []
    for ticket_id, status, verdict, delivered_json, spec_json, inputs_json in connection.exec_driver_sql(
        TICKETS
    ).all():
        binding = {
            "delivered": json.loads(delivered_json),
            "inputs_sha256": _sha256(inputs_json),
            "spec_sha256": _sha256(spec_json),
            "status": status,
            "verdict": verdict,
        }
        found.append((ticket_id, binding))
    for key, table, columns in ROWS:
        for values in connection.exec_driver_sql(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY seq"
        ).all():
            row = {
                column: bool(value) if column in BOOLEANS else value
                for column, value in zip(columns, values, strict=True)
            }
            found.append((NO_TICKET, {key: row}))
    return found


def upgrade() -> None:
    connection = op.get_bind()
    last = connection.exec_driver_sql("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").first()
    prev = last[0] if last else GENESIS
    at = datetime.now(UTC).isoformat(timespec="seconds")  # the format of the ledger's own timestamps
    for ticket_id, binding in _bindings(connection):
        payload_json = _canonical(binding)
        digest = _digest_v2(prev, ticket_id, at, "migrate", "baseline", "", payload_json)
        connection.exec_driver_sql(
            INSERT, (ticket_id, at, "migrate", "baseline", "", prev, digest, 2, payload_json)
        )
        prev = digest


def downgrade() -> None:
    raise NotImplementedError("the registry does not go back: restore the copy agency migrate made")
