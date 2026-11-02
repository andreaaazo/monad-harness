"""Il registro in sola lettura: `mode=ro` e `query_only`, mai `Ledger()`, che all'apertura scrive (ADR-0019).

In WAL chi legge non ferma chi scrive, e viceversa: il cruscotto può leggere mentre il motore lavora.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agency.insights.application import RegistryNotReadable
from agency.insights.domain import TicketRecord, UsageRecord
from agency.insights.ports import RegistrySnapshot

BUSY_SECONDS = 30
# Le colonne nominate una per una, dal modello: una colonna nuova del registro non entra di nascosto.
USAGE = f"SELECT {', '.join(UsageRecord.model_fields)} FROM usage ORDER BY seq"
TICKETS = "SELECT id, spec_json FROM tickets ORDER BY id"
REVISION = "SELECT version_num FROM alembic_version"
HAS_REVISION = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"


class _StoredSpec(BaseModel):
    """Il contratto di un ticket com'è salvato: solo ciò che serve a chi legge, qualunque sia la sua età."""

    model_config = ConfigDict(extra="ignore")

    type: str
    assignee: str
    prompt: str = ""  # i ticket di merlo, prima di M1.5, non lo hanno


class ReadOnlyRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise RegistryNotReadable(f"il registro {self.path} non esiste")
        connection = sqlite3.connect(
            f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_SECONDS
        )
        connection.execute("PRAGMA query_only = ON")
        return connection

    def revision(self) -> str | None:
        with closing(self.connect()) as connection:
            if connection.execute(HAS_REVISION).fetchone() is None:
                return None
            row = connection.execute(REVISION).fetchone()
            return row[0] if row else None

    def read(self) -> RegistrySnapshot:
        with closing(self.connect()) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")  # una sola fotografia per chiamate e ticket
            try:
                usage = [UsageRecord.model_validate(dict(row)) for row in connection.execute(USAGE)]
                tickets = {}
                for ticket_id, spec_json in connection.execute(TICKETS):
                    spec = _StoredSpec.model_validate_json(spec_json)
                    tickets[ticket_id] = TicketRecord(
                        id=ticket_id, type=spec.type, assignee=spec.assignee, prompt=spec.prompt
                    )
            except sqlite3.OperationalError as exc:
                raise RegistryNotReadable(f"il registro non si legge come atteso: {exc}") from exc
            finally:
                connection.rollback()
        return RegistrySnapshot(usage=usage, tickets=tickets)
