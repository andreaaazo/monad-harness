"""Il registro in sola lettura: `mode=ro` e `query_only`, mai `Ledger()`, che all'apertura scrive (ADR-0019).

In WAL chi legge non ferma chi scrive, e viceversa: il cruscotto può leggere mentre il motore lavora.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agency.insights.adapters.stamps import stamp
from agency.insights.application import RegistryNotReadable
from agency.insights.domain import (
    SETBACKS,
    CheckRecord,
    ConceptRecord,
    EventRecord,
    GateRecord,
    JudgmentRecord,
    Lifecycle,
    ProjectRecord,
    RunRecord,
    SourceStamp,
    TicketRecord,
    UsageRecord,
)
from agency.insights.ports import RegistrySnapshot

BUSY_SECONDS = 30
# Le colonne nominate una per una, dal modello: una colonna nuova del registro non entra di nascosto.
USAGE = f"SELECT {', '.join(UsageRecord.model_fields)} FROM usage ORDER BY seq"
TICKETS = "SELECT id, project, spec_json, status, verdict, created_at FROM tickets ORDER BY rowid"
PROJECTS = f"SELECT {', '.join(ProjectRecord.model_fields)} FROM projects ORDER BY name"
GATES = f"SELECT {', '.join(GateRecord.model_fields)} FROM gates ORDER BY seq"
CONCEPTS = "SELECT seq, project, round, letter, anon, lever, status, card_json FROM concepts ORDER BY seq"
JUDGMENTS = (
    "SELECT seq, at, comparison, judge, letter, project, file, sha256, level, specific, best, why,"
    " (SELECT count(*) FROM judgments AS other WHERE other.comparison = judgments.comparison) AS compared"
    " FROM judgments ORDER BY seq"
)
# La storia dei ticket senza le prove, che hanno la loro tabella. La nota si legge solo per un passo indietro,
# dove è il motivo. Il progetto viene dal ticket.
EVENTS = (
    "SELECT events.seq, events.at, tickets.project, events.ticket_id, events.actor, events.action,"
    f" CASE WHEN events.action IN ({', '.join('?' for _ in SETBACKS)}) THEN events.note END AS reason"
    " FROM events JOIN tickets ON tickets.id = events.ticket_id"
    f" WHERE events.action IN ({', '.join('?' for _ in Lifecycle)}) ORDER BY events.seq"
)
EVENT_PARAMETERS = [*sorted(item.value for item in SETBACKS), *(item.value for item in Lifecycle)]
# Le prove, con la loro nota: per un FAIL è il motivo. Prove e file restano dove sono, qui solo l'esito.
CHECKS = (
    "SELECT seq, at, project, ticket_id, file, check_name, result, signer, note AS reason"
    " FROM evidence ORDER BY seq"
)
RUNS = f"SELECT {', '.join(RunRecord.model_fields)} FROM runs ORDER BY seq"
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
        """Una connessione di sola lettura. Un registro WAL chiuso dal motore non ha -shm, e chi legge lo
        crea: se la cartella non si scrive SQLite non lo apre, e lo si dice come un registro illeggibile."""
        if not self.path.is_file():
            raise RegistryNotReadable(f"il registro {self.path} non esiste")
        connection = sqlite3.connect(
            f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_SECONDS
        )
        try:
            connection.execute("PRAGMA query_only = ON")
            # È alla prima lettura che SQLite apre davvero il file, e il suo -shm.
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlite3.OperationalError as exc:
            connection.close()
            raise RegistryNotReadable(f"il registro {self.path} non si apre: {exc}") from exc
        return connection

    def stamp(self) -> list[SourceStamp]:
        """Il file principale e il WAL: con WAL una scrittura cambia il secondo prima del primo.

        Un WAL vuoto vale come assente: non contiene dati, e la prima lettura in sola lettura lo crea. Quando
        i dati passano dal WAL al file principale, cambia l'impronta del principale.
        """
        wal = stamp(self.path.with_name(f"{self.path.name}-wal"))
        if wal.size == 0:
            wal = SourceStamp(name=wal.name, size=None, modified_ns=None)
        return [stamp(self.path), wal]

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
                    events=[
                        EventRecord.model_validate(dict(row))
                        for row in connection.execute(EVENTS, EVENT_PARAMETERS)
                    ],
                    checks=[CheckRecord.model_validate(dict(row)) for row in connection.execute(CHECKS)],
                    runs=[RunRecord.model_validate(dict(row)) for row in connection.execute(RUNS)],
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
