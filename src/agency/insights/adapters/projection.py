"""La proiezione in `.data/insights.sqlite`: si cancella e si rigenera, la verità resta nel registro.

Si scrive sempre per intero in un file accanto, che prende il posto del vecchio solo quando è completo: chi
sta leggendo continua sulla sua versione, chi apre dopo trova la nuova. Le colonne nascono dal modello
`Call`, e `user_version` dice lo schema: una proiezione di uno schema diverso non si legge, si rigenera.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import types
from contextlib import closing
from enum import StrEnum
from pathlib import Path
from typing import get_args

from pydantic.fields import FieldInfo

from agency.insights.application import ProjectionOutdated
from agency.insights.domain import Call, Provenance

COLUMNS = list(Call.model_fields)


def _column(name: str, info: FieldInfo) -> str:
    kind = info.annotation
    nullable = isinstance(kind, types.UnionType) and type(None) in get_args(kind)
    if nullable:
        (kind,) = (arg for arg in get_args(kind) if arg is not type(None))
    if kind is int:
        sql = "INTEGER"
    elif kind is float:
        sql = "REAL"
    elif kind is str or (isinstance(kind, type) and issubclass(kind, StrEnum)):
        sql = "TEXT"
    else:
        raise TypeError(f"{name}: tipo {kind!r} senza colonna SQLite")
    key = " PRIMARY KEY" if name == "seq" else ""
    return f"{name} {sql}{'' if nullable else ' NOT NULL'}{key}"


CREATE_CALLS = f"CREATE TABLE calls ({', '.join(_column(n, i) for n, i in Call.model_fields.items())})"
INSERT_CALL = f"INSERT INTO calls ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})"
SELECT_CALLS = f"SELECT {', '.join(COLUMNS)} FROM calls"


class SqliteProjection:
    SCHEMA = 1

    def __init__(self, path: Path) -> None:
        self.path = path

    def replace(self, calls: list[Call], provenance: Provenance) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        os.close(descriptor)
        temporary = Path(name)
        try:
            with closing(sqlite3.connect(temporary)) as connection:
                connection.execute(CREATE_CALLS)
                connection.execute("CREATE INDEX ix_calls_project ON calls (project)")
                connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                rows = (tuple(call.model_dump(mode="json")[column] for column in COLUMNS) for call in calls)
                connection.executemany(INSERT_CALL, rows)
                connection.execute(
                    "INSERT INTO meta VALUES ('provenance', ?)", (provenance.model_dump_json(),)
                )
                connection.execute(f"PRAGMA user_version = {self.SCHEMA}")
                connection.commit()
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise ProjectionOutdated("la proiezione non c'è ancora: esegui agency insights")
        connection = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != self.SCHEMA:
            connection.close()
            raise ProjectionOutdated(
                f"proiezione allo schema {version}, serve il {self.SCHEMA}: esegui agency insights"
            )
        return connection

    def calls(self, project: str | None = None) -> list[Call]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            if project is None:
                rows = connection.execute(f"{SELECT_CALLS} ORDER BY seq")
            else:
                rows = connection.execute(f"{SELECT_CALLS} WHERE project = ? ORDER BY seq", (project,))
            return [Call.model_validate(dict(row)) for row in rows]

    def provenance(self) -> Provenance:
        with closing(self._connect()) as connection:
            (value,) = connection.execute("SELECT value FROM meta WHERE key = 'provenance'").fetchone()
            return Provenance.model_validate_json(value)
