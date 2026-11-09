"""Lo schema del registro: nasce dalle migrazioni e si aggiorna solo su richiesta (ADR-0022).

Un registro nuovo si crea da solo. Uno esistente non si tocca mai aprendolo: aggiornarlo è un'azione
esplicita, che fa prima una copia e lavora in una sola transazione. Alembic su SQLite non è transazionale
di suo: lo diventa perché riceve una connessione con la transazione già aperta, e il commit avviene qui,
solo a catena verificata.
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
    """Il registro non è alla revisione del codice: si aggiorna con `agency migrate`."""


class LedgerMismatch(Exception):
    """Lo schema non è quello atteso: non si adotta un registro che non si riconosce."""


class ChainBroken(Exception):
    """La catena di hash non regge: la migrazione non si conferma."""


@dataclass(frozen=True)
class Migration:
    revision: str
    backup: Path | None


def _config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS).replace("%", "%%"))
    config.attributes["connection"] = connection
    return config


def head() -> str:
    revision = ScriptDirectory.from_config(_config()).get_current_head()
    if revision is None:
        raise RuntimeError("nessuna migrazione trovata")
    return revision


def revision_of(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def objects(connection: Connection) -> dict[tuple[str, str], str]:
    """Tabelle, indici e trigger, con gli spazi normalizzati: `alembic_version` è di Alembic."""
    rows = connection.exec_driver_sql(CATALOG)
    return {(kind, name): " ".join(sql.split()) for kind, name, sql in rows if name != "alembic_version"}


def baseline() -> dict[tuple[str, str], str]:
    """Lo schema di partenza, ricavato dalla sua migrazione su un database vuoto."""
    with create_engine("sqlite://").begin() as connection:
        command.upgrade(_config(connection), BASELINE)
        return objects(connection)


def ensure_current(engine: Engine) -> None:
    with engine.connect() as connection:
        if revision_of(connection) == head():
            return
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")  # due processi possono aprire il registro insieme
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
