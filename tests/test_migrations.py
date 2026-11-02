"""Il registro nasce dalle migrazioni e si aggiorna solo su richiesta, senza perdere nulla (ADR-0022)."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlmodel import SQLModel

from agency import cli
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger, LedgerOutdated, chain, schema
from agency.ledger.schema import ChainBroken, LedgerMismatch, migrate

REAL_SCHEMA = Path(__file__).parent / "fixtures" / "ledger_schema_0001.sql"
CATALOG = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"


def catalog(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    rows = connection.execute(CATALOG).fetchall()
    return {(kind, name): " ".join(sql.split()) for kind, name, sql in rows if name != "alembic_version"}


def read(path: Path, query: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(query).fetchall()


def filled(path: Path) -> None:
    """Un registro con una storia: un ticket e i suoi eventi concatenati."""
    ledger = Ledger(path)
    spec = TicketSpec(
        title="Logo",
        request="Disegna",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=["segno.svg"],
        checks={"*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
    )
    ticket = ledger.open(spec, "prova")
    ledger.apply(ticket, Action.BLOCK, "identity-designer", "manca il brief")
    ledger.engine.dispose()


USAGE = (
    "INSERT INTO usage (at, project, ticket_id, role, instance, model, input_tokens, output_tokens,"
    " cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cost_usd, stop_reason, request_id)"
    " VALUES ('2026-10-31T10:00:00+00:00', 'prova', 'T-0001', 'identity-designer', 'i',"
    " 'claude-opus-5-5', 100, 20, 0, 0, 0, 0.01, 'tool_use', 'req_1')"
)
EVENT = (
    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?, ?)"
)


def before_migrations(path: Path) -> None:
    """Un registro com'era prima di Alembic: lo schema reale di allora, una storia concatenata."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(REAL_SCHEMA.read_text(encoding="utf-8"))
        connection.execute(USAGE)
        previous, at = chain.GENESIS, "2026-10-31T10:00:00+00:00"
        for action, note in (("open", "Logo"), ("block", "manca il brief")):
            digest = chain.digest(previous, "T-0001", at, "identity-designer", action, note)
            connection.execute(EVENT, ("T-0001", at, "identity-designer", action, note, previous, digest))
            previous = digest
        connection.commit()


def at_baseline(path: Path) -> None:
    """Un registro già adottato da `agency migrate` alla prima revisione, prima che esistesse `runs`."""
    before_migrations(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL,"
            " CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        connection.execute("INSERT INTO alembic_version VALUES (?)", (schema.BASELINE,))
        connection.commit()


def add_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    """Aggiunge una migrazione alle reali, su una copia: quelle del progetto non si toccano."""
    folder = tmp_path / "migrations"
    shutil.copytree(schema.MIGRATIONS, folder, ignore=shutil.ignore_patterns("__pycache__"))
    previous = schema.head()
    (folder / "versions" / "9999_prova.py").write_text(
        f'from alembic import op\nrevision = "9999"\ndown_revision = "{previous}"\n'
        f"def upgrade() -> None:\n{body}",
        encoding="utf-8",
    )
    monkeypatch.setattr(schema, "MIGRATIONS", folder)


def test_baseline_is_the_schema_of_the_real_registry() -> None:
    with closing(sqlite3.connect(":memory:")) as real:
        real.executescript(REAL_SCHEMA.read_text(encoding="utf-8"))
        expected = catalog(real)
    assert len(expected) == 37
    assert schema.baseline() == expected


def test_models_and_migrations_do_not_diverge(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    with ledger.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), SQLModel.metadata) == []


def test_new_registry_is_created_at_the_latest_revision(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    Ledger(path)
    assert read(path, "SELECT version_num FROM alembic_version") == [(schema.head(),)]


def test_registry_can_be_created_by_two_openers_together(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    start = threading.Barrier(4)
    failures: list[Exception] = []

    def open_it() -> None:
        start.wait()
        try:
            Ledger(path)
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=open_it) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert failures == []
    assert read(path, "SELECT count(*) FROM alembic_version") == [(1,)]


def test_outdated_registry_is_never_changed_by_opening_it(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    before_migrations(path)
    tables = read(path, CATALOG)
    with pytest.raises(LedgerOutdated, match="agency migrate"):
        Ledger(path)
    assert read(path, CATALOG) == tables


def test_migrate_adopts_a_registry_older_than_the_migrations(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    before_migrations(path)
    events = read(path, "SELECT * FROM events ORDER BY seq")
    assert len(events) == 2

    result = migrate(path)

    assert result.revision == schema.head()
    assert read(path, "SELECT * FROM events ORDER BY seq") == events
    assert Ledger(path).verify_chain()


def test_migrate_adds_the_new_tables_to_a_registry_at_the_baseline_and_keeps_every_row(
    tmp_path: Path,
) -> None:
    path = tmp_path / "l.sqlite"
    at_baseline(path)
    tables = [name for (name,) in read(path, "SELECT name FROM sqlite_master WHERE type = 'table'")]
    columns = {table: [row[1] for row in read(path, f"PRAGMA table_info({table})")] for table in tables}
    columns.pop("alembic_version")
    selects = {table: f"SELECT {', '.join(names)} FROM {table}" for table, names in columns.items()}
    rows = {table: read(path, query) for table, query in selects.items()}

    assert migrate(path).revision == schema.head()

    assert {table: read(path, query) for table, query in selects.items()} == rows
    added = "run, phase, effort, duration_ms, ttft_ms, reasoning_tokens"
    assert read(path, f"SELECT {added} FROM usage") == [(None,) * 6]
    for table in ("runs", "judgments", "artifacts"):
        assert read(path, f"SELECT count(*) FROM {table}") == [(0,)]
        triggers = read(
            path, f"SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = '{table}'"
        )
        assert sorted(triggers) == [(f"{table}_no_delete",), (f"{table}_no_update",)]
    assert Ledger(path).verify_chain()


def test_registry_at_the_baseline_is_refused_until_it_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    at_baseline(path)
    with pytest.raises(LedgerOutdated, match=f"revisione {schema.BASELINE}.*agency migrate"):
        Ledger(path)


def test_migrate_keeps_a_copy_of_the_registry_as_it_was(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    before_migrations(path)
    events = read(path, "SELECT * FROM events ORDER BY seq")

    backup = migrate(path).backup

    assert backup is not None
    assert backup.parent == tmp_path / "backups"
    assert read(backup, "SELECT * FROM events ORDER BY seq") == events
    assert read(backup, "SELECT name FROM sqlite_master WHERE name = 'alembic_version'") == []


def test_migrate_applies_new_migrations_after_the_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "l.sqlite"
    filled(path)
    add_migration(tmp_path, monkeypatch, '    op.execute("ALTER TABLE usage ADD COLUMN prova_ms INTEGER")\n')

    assert migrate(path).revision == "9999"

    columns = [row[1] for row in read(path, "PRAGMA table_info(usage)")]
    assert "prova_ms" in columns
    assert read(path, "SELECT version_num FROM alembic_version") == [("9999",)]


def test_migrate_on_an_updated_registry_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    filled(path)
    result = migrate(path)
    assert (result.revision, result.backup) == (schema.head(), None)
    assert not (tmp_path / "backups").exists()


def test_migrate_refuses_a_schema_it_does_not_recognise(tmp_path: Path) -> None:
    path = tmp_path / "l.sqlite"
    before_migrations(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DROP TRIGGER events_no_update")
        connection.commit()

    with pytest.raises(LedgerMismatch, match="events_no_update"):
        migrate(path)

    assert read(path, "SELECT name FROM sqlite_master WHERE name = 'alembic_version'") == []
    assert not (tmp_path / "backups").exists()


def test_failed_migration_leaves_the_registry_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "l.sqlite"
    filled(path)
    add_migration(
        tmp_path,
        monkeypatch,
        '    op.execute("CREATE TABLE mezza (id INTEGER)")\n    raise RuntimeError("guasto a metà")\n',
    )

    with pytest.raises(RuntimeError, match="guasto a metà"):
        migrate(path)

    assert read(path, "SELECT name FROM sqlite_master WHERE name = 'mezza'") == []
    monkeypatch.undo()
    assert read(path, "SELECT version_num FROM alembic_version") == [(schema.head(),)]
    assert Ledger(path).verify_chain()


def test_migration_that_breaks_the_chain_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "l.sqlite"
    filled(path)
    notes = read(path, "SELECT note FROM events ORDER BY seq")
    add_migration(
        tmp_path,
        monkeypatch,
        '    op.execute("DROP TRIGGER events_no_update")\n'
        "    op.execute(\"UPDATE events SET note = 'riscritta'\")\n",
    )

    with pytest.raises(ChainBroken):
        migrate(path)

    assert read(path, "SELECT note FROM events ORDER BY seq") == notes
    assert read(path, "SELECT name FROM sqlite_master WHERE name = 'events_no_update'") != []


def test_commands_refuse_an_outdated_registry_and_say_what_to_do(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    before_migrations(tmp_path / "ledger.sqlite")
    assert cli.main(["verify"]) == 1
    assert "agency migrate" in capsys.readouterr().out


def test_agency_migrate_reports_the_copy_and_the_commands_work_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    before_migrations(tmp_path / "ledger.sqlite")
    assert cli.main(["migrate"]) == 0
    assert str(tmp_path / "backups") in capsys.readouterr().out
    assert cli.main(["verify"]) == 0


def test_agency_migrate_without_a_registry_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    assert cli.main(["migrate"]) == 0
    assert "nessun registro" in capsys.readouterr().out.lower()
    assert not (tmp_path / "ledger.sqlite").exists()
