"""The registry schema: it comes from the migrations and is updated only on request (ADR-0022, ADR-0025).

A new registry creates itself. An existing one is never touched when it is opened: updating it is an
explicit action, which first makes a copy and works in a single transaction. Alembic on SQLite is not
transactional on its own: it becomes so because it receives a connection whose transaction is already open,
and the commit happens here, only once the chain is verified.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine

from agency.ledger import chain

MIGRATIONS = Path(__file__).parent / "migrations"
BASELINE = "0001"
BUSY_SECONDS = 30
EVENTS = (
    "SELECT ticket_id, at, actor, action, note, prev_hash, hash, version, payload_json"
    " FROM events ORDER BY seq"
)
CATALOG = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"


class LedgerOutdated(Exception):
    """The registry is not at the code's revision: `agency migrate` updates it."""


class LedgerMismatch(Exception):
    """The schema is not the expected one: a registry that is not recognised is not adopted."""


class ChainBroken(Exception):
    """The hash chain does not hold: the migration is not committed."""


@dataclass(frozen=True)
class Migration:
    """A finished `migrate`: the revision reached, and the backup made first (None if nothing changed)."""

    revision: str
    backup: Path | None


def _config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS).replace("%", "%%"))
    config.attributes["connection"] = connection
    return config


def head() -> str:
    """The revision of the latest migration: the one the code wants."""
    revision = ScriptDirectory.from_config(_config()).get_current_head()
    if revision is None:
        raise RuntimeError("no migration found")
    return revision


def revision_of(connection: Connection) -> str | None:
    """The registry's Alembic revision, or None for a registry from before the migrations."""
    return MigrationContext.configure(connection).get_current_revision()


def objects(connection: Connection) -> dict[tuple[str, str], str]:
    """Tables, indexes and triggers, whitespace normalised; `alembic_version` belongs to Alembic."""
    rows = connection.exec_driver_sql(CATALOG)
    return {(kind, name): " ".join(sql.split()) for kind, name, sql in rows if name != "alembic_version"}


def baseline() -> dict[tuple[str, str], str]:
    """The starting schema, derived from its migration on an empty database."""
    with create_engine("sqlite://").begin() as connection:
        command.upgrade(_config(connection), BASELINE)
        return objects(connection)


def ensure_current(engine: Engine) -> None:
    """Creates an empty registry at the head; an existing one at another revision raises `LedgerOutdated`."""
    with engine.connect() as connection:
        if revision_of(connection) == head():
            return
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")  # two processes can open the registry at the same time
        found = revision_of(connection)
        if not objects(connection):
            command.upgrade(_config(connection), "head")
        elif found != head():
            state = f"alla revisione {found}" if found else "precedente alle migrazioni"
            raise LedgerOutdated(f"registro {state}, il codice vuole la {head()}: esegui agency migrate")


def _recognise(connection: Connection) -> None:
    different = {key[1] for key, _ in objects(connection).items() ^ baseline().items()}
    if different:
        raise LedgerMismatch(f"schema non riconosciuto, differiscono: {', '.join(sorted(different))}")


def _backup(path: Path, revision: str | None) -> Path:
    folder = path.parent / "backups"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = folder / f"{path.stem}-{revision or 'prima-di-alembic'}-{stamp}.sqlite"
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(sqlite3.connect(target)) as copy:
        source.backup(copy)
    return target


def migrate(path: Path) -> Migration:
    """Brings the registry to the head: a backup first, then one transaction, committed only if the chain
    holds. A registry from before Alembic is adopted only if its schema is the baseline's."""
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": BUSY_SECONDS})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            found, target = revision_of(connection), head()
            if found == target:
                return Migration(target, None)
            if found is None:
                _recognise(connection)
            backup = _backup(path, found)
            if found is None:
                command.stamp(_config(connection), BASELINE)
            command.upgrade(_config(connection), "head")
            if not chain.intact(connection.exec_driver_sql(EVENTS)):
                raise ChainBroken(f"la catena di hash non regge dopo la migrazione. Copia: {backup}")
            connection.commit()
        return Migration(target, backup)
    finally:
        engine.dispose()
