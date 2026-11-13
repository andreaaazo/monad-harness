"""The registry, read-only: `mode=ro` and `query_only`, never `Ledger()`, which writes when it opens
(ADR-0019).

With WAL, readers do not block the writer and the writer does not block them: the dashboard can read while
the engine works.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agency.insights.adapters.stamps import stamp
from agency.insights.application import LedgerNotReadable
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
from agency.insights.ports import LedgerSnapshot

BUSY_SECONDS = 30
# The columns are named one by one, from the model, so a new registry column cannot slip in unseen.
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
# The tickets' history without the proofs, which have their own table. The note is read only for a step
# back, where it is the reason. The project comes from the ticket.
EVENTS = (
    "SELECT events.seq, events.at, tickets.project, events.ticket_id, events.actor, events.action,"
    f" CASE WHEN events.action IN ({', '.join('?' for _ in SETBACKS)}) THEN events.note END AS reason"
    " FROM events JOIN tickets ON tickets.id = events.ticket_id"
    f" WHERE events.action IN ({', '.join('?' for _ in Lifecycle)}) ORDER BY events.seq"
)
EVENT_PARAMETERS = [*sorted(item.value for item in SETBACKS), *(item.value for item in Lifecycle)]
# The proofs, with their note: for a FAIL it is the reason. Proofs and files stay where they are; only the
# result is read here.
CHECKS = (
    "SELECT seq, at, project, ticket_id, file, check_name, result, signer, note AS reason"
    " FROM evidence ORDER BY seq"
)
RUNS = f"SELECT {', '.join(RunRecord.model_fields)} FROM runs ORDER BY seq"
REVISION = "SELECT version_num FROM alembic_version"
HAS_REVISION = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"


class _StoredSpec(BaseModel):
    """A ticket's contract as stored: only what a reader needs, whatever its age."""

    model_config = ConfigDict(extra="ignore")

    type: str
    assignee: str
    title: str
    prompt: str = ""  # merlo's tickets, from before M1.5, lack it


class _StoredCard(BaseModel):
    """An idea's card as stored: only its sentence is needed."""

    model_config = ConfigDict(extra="ignore")

    concept: str = ""  # an idea not delivered yet has an empty card


class ReadOnlyLedger:
    """The `LedgerReader` on the SQLite file, which it never writes."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        """A read-only connection. A WAL registry closed by the engine has no -shm file, and the reader
        creates it: if the folder is not writable SQLite cannot open it, and the registry is reported as
        unreadable."""
        if not self.path.is_file():
            raise LedgerNotReadable(f"il registro {self.path} non esiste")
        connection = sqlite3.connect(
            f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_SECONDS
        )
        try:
            connection.execute("PRAGMA query_only = ON")
            # SQLite really opens the file, and its -shm, on the first read.
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlite3.OperationalError as exc:
            connection.close()
            raise LedgerNotReadable(f"il registro {self.path} non si apre: {exc}") from exc
        return connection

    def stamp(self) -> list[SourceStamp]:
        """The main file and the WAL: with WAL, a write changes the second before the first.

        An empty WAL counts as missing: it holds no data, and the first read-only read creates it. When the
        data moves from the WAL into the main file, the main file's stamp changes.
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

    def read(self) -> LedgerSnapshot:
        with closing(self.connect()) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")  # one snapshot of everything that is read
            try:
                return LedgerSnapshot(
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
                raise LedgerNotReadable(f"il registro non si legge come atteso: {exc}") from exc
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
