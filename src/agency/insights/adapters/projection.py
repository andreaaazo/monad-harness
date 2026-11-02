"""La proiezione in `.data/insights.sqlite`: si cancella e si rigenera, la verità resta nel registro.

Si scrive sempre per intero in un file accanto, che prende il posto del vecchio solo quando è completo: chi
sta leggendo continua sulla sua versione, chi apre dopo trova la nuova. Ogni tabella nasce dal suo modello,
colonna per colonna, e `user_version` dice lo schema: una proiezione di uno schema diverso non si legge, si
rigenera.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import types
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import get_args

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from agency.insights.application import ProjectionOutdated
from agency.insights.domain import (
    Call,
    ConceptRecord,
    GateRecord,
    JudgmentRecord,
    Projected,
    ProjectRecord,
    Provenance,
    TicketRecord,
)
from agency.insights.ports import ProjectData


def _column(name: str, info: FieldInfo, key: str) -> str:
    kind = info.annotation
    nullable = isinstance(kind, types.UnionType) and type(None) in get_args(kind)
    if nullable:
        (kind,) = (arg for arg in get_args(kind) if arg is not type(None))
    if kind is bool or kind is int:
        sql = "INTEGER"
    elif kind is float:
        sql = "REAL"
    elif kind is str or (isinstance(kind, type) and issubclass(kind, StrEnum)):
        sql = "TEXT"
    else:
        raise TypeError(f"{name}: tipo {kind!r} senza colonna SQLite")
    return f"{name} {sql}{'' if nullable else ' NOT NULL'}{' PRIMARY KEY' if name == key else ''}"


@dataclass(frozen=True)
class _Table[T: BaseModel]:
    name: str
    model: type[T]
    key: str
    scope: str = "project"  # la colonna con cui si legge un progetto

    @property
    def columns(self) -> list[str]:
        return list(self.model.model_fields)

    def create(self) -> list[str]:
        columns = ", ".join(_column(name, info, self.key) for name, info in self.model.model_fields.items())
        statements = [f"CREATE TABLE {self.name} ({columns})"]
        if self.scope != self.key:
            statements.append(f"CREATE INDEX ix_{self.name}_{self.scope} ON {self.name} ({self.scope})")
        return statements

    def insert(self) -> str:
        places = ", ".join("?" for _ in self.columns)
        return f"INSERT INTO {self.name} ({', '.join(self.columns)}) VALUES ({places})"

    def select(self, scoped: bool) -> str:
        where = f" WHERE {self.scope} = ?" if scoped else ""
        return f"SELECT {', '.join(self.columns)} FROM {self.name}{where} ORDER BY {self.key}"

    def rows(self, items: list[T]) -> list[tuple[object, ...]]:
        return [tuple(item.model_dump(mode="json")[column] for column in self.columns) for item in items]


CALLS = _Table("calls", Call, "seq")
PROJECTS = _Table("projects", ProjectRecord, "name", scope="name")
TICKETS = _Table("tickets", TicketRecord, "id")
GATES = _Table("gates", GateRecord, "seq")
CONCEPTS = _Table("concepts", ConceptRecord, "seq")
JUDGMENTS = _Table("judgments", JudgmentRecord, "seq")


class SqliteProjection:
    SCHEMA = 3

    def __init__(self, path: Path) -> None:
        self.path = path

    def replace(self, projected: Projected, provenance: Provenance) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        os.close(descriptor)
        temporary = Path(name)
        try:
            with closing(sqlite3.connect(temporary)) as connection:
                self._write(connection, CALLS, projected.calls)
                self._write(connection, PROJECTS, projected.projects)
                self._write(connection, TICKETS, projected.tickets)
                self._write(connection, GATES, projected.gates)
                self._write(connection, CONCEPTS, projected.concepts)
                self._write(connection, JUDGMENTS, projected.judgments)
                connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
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
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _write[T: BaseModel](connection: sqlite3.Connection, table: _Table[T], items: list[T]) -> None:
        for statement in table.create():
            connection.execute(statement)
        connection.executemany(table.insert(), table.rows(items))

    @staticmethod
    def _read[T: BaseModel](connection: sqlite3.Connection, table: _Table[T], scope: str | None) -> list[T]:
        rows = connection.execute(table.select(scope is not None), () if scope is None else (scope,))
        return [table.model.model_validate(dict(row)) for row in rows]

    def calls(self, project: str | None = None) -> list[Call]:
        with closing(self._connect()) as connection:
            return self._read(connection, CALLS, project)

    def projects(self) -> list[ProjectRecord]:
        with closing(self._connect()) as connection:
            return self._read(connection, PROJECTS, None)

    def project(self, name: str) -> ProjectData:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")  # le parti di un progetto dalla stessa versione della proiezione
            projects = self._read(connection, PROJECTS, name)
            return ProjectData(
                project=projects[0] if projects else None,
                calls=self._read(connection, CALLS, name),
                tickets=self._read(connection, TICKETS, name),
                gates=self._read(connection, GATES, name),
                concepts=self._read(connection, CONCEPTS, name),
                judgments=self._read(connection, JUDGMENTS, name),
            )

    def provenance(self) -> Provenance:
        with closing(self._connect()) as connection:
            (value,) = connection.execute("SELECT value FROM meta WHERE key = 'provenance'").fetchone()
            return Provenance.model_validate_json(value)
