"""Il registro in sola lettura: `mode=ro` e `query_only`, mai `Ledger()`, che all'apertura scrive (ADR-0019).

In WAL chi legge non ferma chi scrive, e viceversa: il cruscotto può leggere mentre il motore lavora.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agency.insights.application import RegistryNotReadable
from agency.insights.domain import (
    ConceptRecord,
    GateRecord,
    JudgmentRecord,
    ProjectRecord,
    TicketRecord,
    UsageRecord,
)
from agency.insights.ports import RegistrySnapshot

BUSY_SECONDS = 30
# Le colonne nominate una per una, dal modello: una colonna nuova del registro non entra di nascosto.
USAGE = f"SELECT {', '.join(UsageRecord.model_fields)} FROM usage ORDER BY seq"
TICKETS = "SELECT id, project, spec_json, status, verdict, created_at FROM tickets ORDER BY id"
PROJECTS = f"SELECT {', '.join(ProjectRecord.model_fields)} FROM projects ORDER BY name"
GATES = f"SELECT {', '.join(GateRecord.model_fields)} FROM gates ORDER BY seq"
CONCEPTS = "SELECT seq, project, round, letter, anon, lever, status, card_json FROM concepts ORDER BY seq"
JUDGMENTS = (
    "SELECT seq, at, comparison, judge, letter, project, file, sha256, level, specific, best, why,"
    " (SELECT count(*) FROM judgments AS other WHERE other.comparison = judgments.comparison) AS compared"
    " FROM judgments ORDER BY seq"
)
REVISION = "SELECT version_num FROM alembic_version"
HAS_REVISION = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"


class _StoredSpec(BaseModel):
    """Il contratto di un ticket com'è salvato: solo ciò che serve a chi legge, qualunque sia la sua età."""

    model_config = ConfigDict(extra="ignore")

    type: str
    assignee: str
    title: str
    prompt: str = ""  # i ticket di merlo, prima di M1.5, non lo hanno


class _StoredCard(BaseModel):
    """La scheda di un'idea com'è salvata: della scheda serve solo la frase."""

    model_config = ConfigDict(extra="ignore")

    concept: str = ""  # un'idea non ancora consegnata ha la scheda vuota


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
            connection.execute("BEGIN")  # una sola fotografia di tutto ciò che si legge
            try:
                return RegistrySnapshot(
                    usage=[UsageRecord.model_validate(dict(row)) for row in connection.execute(USAGE)],
                    tickets={ticket.id: ticket for ticket in map(_ticket, connection.execute(TICKETS))},
                    projects=[
                        ProjectRecord.model_validate(dict(row)) for row in connection.execute(PROJECTS)
                    ],
                    gates=[GateRecord.model_validate(dict(row)) for row in connection.execute(GATES)],
                    concepts=[_concept(row) for row in connection.execute(CONCEPTS)],
                    judgments=[
                        JudgmentRecord.model_validate(dict(row)) for row in connection.execute(JUDGMENTS)
                    ],
                )
            except sqlite3.OperationalError as exc:
                raise RegistryNotReadable(f"il registro non si legge come atteso: {exc}") from exc
            finally:
                connection.rollback()


def _ticket(row: sqlite3.Row) -> TicketRecord:
    spec = _StoredSpec.model_validate_json(row["spec_json"])
    return TicketRecord(
        id=row["id"],
        project=row["project"],
        type=spec.type,
        assignee=spec.assignee,
        prompt=spec.prompt,
        title=spec.title,
        status=row["status"],
        verdict=row["verdict"],
        created_at=row["created_at"],
    )


def _concept(row: sqlite3.Row) -> ConceptRecord:
    return ConceptRecord(
        seq=row["seq"],
        project=row["project"],
        round=row["round"],
        letter=row["letter"],
        anon=row["anon"],
        lever=row["lever"],
        status=row["status"],
        concept=_StoredCard.model_validate_json(row["card_json"]).concept,
    )
