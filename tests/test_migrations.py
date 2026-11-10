"""Il registro nasce dalle migrazioni e si aggiorna solo su richiesta, senza perdere nulla (ADR-0022)."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
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


def migrations_up_to(tmp_path: Path, revision: str) -> Path:
    """A copy of the real migrations without those after `revision`: the project's own are not touched."""
    folder = tmp_path / f"migrations-{revision}"
    shutil.copytree(schema.MIGRATIONS, folder, ignore=shutil.ignore_patterns("__pycache__"))
    for later in (folder / "versions").glob("*.py"):
        if later.name[:4] > revision:
            later.unlink()
    return folder


LOGO = TicketSpec(
    title="Logo",
    request="Disegna",
    type=TicketType.PRODUCTION,
    sender="design-director",
    assignee="identity-designer",
    outputs=["segno.svg"],
    checks={"*.svg": ["svg_audit"]},
    media=[Medium.VECTOR],
)
REVIEW = TicketSpec.model_validate(
    LOGO.model_dump() | {"title": "Verifica", "type": TicketType.QA, "assignee": "qa-inspector", "media": []}
)
TICKET = (
    "INSERT INTO tickets (id, project, spec_json, status, verdict, delivered_json, inputs_json, created_at)"
    " VALUES (?, 'prova', ?, ?, ?, ?, '{}', '2026-11-01T10:00:00+00:00')"
)
# Each ticket of a registry at revision 0005: its spec, status, verdict and delivered hashes, and the
# version-1 events that led there as (actor, action, note).
BEFORE_0006 = (
    ("T-0001", LOGO, "open", None, {}, (("design-director", "open", "Logo"),)),
    (
        "T-0002",
        REVIEW,
        "delivered",
        "READY",
        {"segno.svg": "a1b2"},
        (("design-director", "open", "Verifica"), ("qa-inspector", "deliver", "")),
    ),
    (
        "T-0003",
        REVIEW,
        "rework",
        None,
        {"segno.svg": "c3d4"},
        (
            ("design-director", "open", "Verifica"),
            ("qa-inspector", "deliver", ""),
            ("design-director", "rework", "rifai la verifica"),
        ),
    ),
    (
        "T-0004",
        LOGO,
        "accepted",
        None,
        {"segno.svg": "e5f6"},
        (
            ("design-director", "open", "Logo"),
            ("identity-designer", "deliver", ""),
            ("design-director", "accept", ""),
        ),
    ),
)
V1_COLUMNS = "seq, ticket_id, at, actor, action, note, prev_hash, hash"


def at_revision_0005(path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry at revision 0005, before events bound the ticket state: tickets in several states and the
    version-1 events that led there."""
    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", migrations_up_to(tmp_path, "0005"))
        engine = create_engine(f"sqlite:///{path}")
        schema.ensure_current(engine)
        engine.dispose()
    with closing(sqlite3.connect(path)) as connection:
        previous, at = chain.GENESIS, "2026-11-01T10:00:00+00:00"
        for ticket, spec, status, verdict, delivered, history in BEFORE_0006:
            connection.execute(
                TICKET, (ticket, spec.model_dump_json(), status, verdict, json.dumps(delivered))
            )
            for actor, action, note in history:
                digest = chain.digest(previous, ticket, at, actor, action, note)
                connection.execute(EVENT, (ticket, at, actor, action, note, previous, digest))
                previous = digest
        connection.commit()


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
    after = read(path, f"SELECT {V1_COLUMNS} FROM events ORDER BY seq")
    assert after[:2] == events
    assert [(row[1], row[3], row[4]) for row in after[2:]] == [("-", "migrate", "baseline")]  # the paid call
    assert read(path, "SELECT version, payload_json FROM events ORDER BY seq")[:2] == [(1, "")] * 2
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

    after = {table: read(path, query) for table, query in selects.items()}
    events = rows.pop("events")
    assert after.pop("events")[: len(events)] == events  # 0008 adds the baseline of the paid call
    assert after == rows
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


def test_migration_binds_every_ticket_state_into_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One baseline event per ticket binds the state `tickets` holds, with the real time of the migration; the
    events written before stay as they were (ADR-0047)."""
    path = tmp_path / "l.sqlite"
    at_revision_0005(path, tmp_path, monkeypatch)
    assert read(path, "SELECT version_num FROM alembic_version") == [("0005",)]
    before = read(path, f"SELECT {V1_COLUMNS} FROM events ORDER BY seq")
    started = datetime.now(UTC).replace(microsecond=0)

    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", migrations_up_to(tmp_path, "0006"))
        assert migrate(path).revision == "0006"

    events = read(path, f"SELECT {V1_COLUMNS}, version, payload_json FROM events ORDER BY seq")
    old, added = events[: len(before)], events[len(before) :]
    assert [row[:8] for row in old] == before
    assert {row[8:] for row in old} == {(1, "")}
    assert [(row[1], row[3], row[4], row[5], row[8]) for row in added] == [
        (ticket, "migrate", "baseline", "", 2) for ticket, *_ in BEFORE_0006
    ]
    states = [(status, verdict, delivered) for _, _, status, verdict, delivered, _ in BEFORE_0006]
    assert [json.loads(row[9]) for row in added] == [
        {"status": status, "verdict": verdict, "delivered": delivered}
        for status, verdict, delivered in states
    ]
    assert [row[9] for row in added] == [
        chain.canonical({"delivered": delivered, "status": status, "verdict": verdict})
        for status, verdict, delivered in states
    ]
    (stamp,) = {row[2] for row in added}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", stamp)
    assert started <= datetime.fromisoformat(stamp) <= datetime.now(UTC)
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert chain.intact(connection.exec_driver_sql(schema.EVENTS))
    engine.dispose()


def test_v1_events_still_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each event is checked with the formula of its version: old rows are never rewritten (ADR-0047)."""
    path = tmp_path / "l.sqlite"
    at_revision_0005(path, tmp_path, monkeypatch)
    migrate(path)
    ledger = Ledger(path)
    ledger.apply("T-0001", Action.BLOCK, "identity-designer", "manca il brief")
    # 9 version-1 events, a baseline per ticket from 0006 and from 0007, and the block
    assert [version for (version,) in read(path, "SELECT version FROM events ORDER BY seq")] == [1] * 9 + [
        2
    ] * 9
    assert ledger.verify_chain()

    def intact_after(statement: str) -> bool:
        with ledger.engine.begin() as connection:
            connection.execute(text("DROP TRIGGER IF EXISTS events_no_update"))
            connection.execute(text(statement))
        return ledger.verify_chain()

    assert not intact_after("UPDATE events SET note = 'riscritta' WHERE seq = 1")
    assert intact_after("UPDATE events SET note = 'Logo' WHERE seq = 1")
    verdict = "UPDATE events SET payload_json = replace(payload_json, '{0}', '{1}') WHERE action = 'baseline'"
    assert not intact_after(verdict.format("READY", "REVISE"))
    assert intact_after(verdict.format("REVISE", "READY"))
    assert not intact_after("UPDATE events SET version = 3 WHERE seq = 14")


def at_revision_0006(path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry at revision 0006: the tickets of `at_revision_0005` with their state bound by 0006, and an
    idea, a gate and a proof that no event binds yet."""
    at_revision_0005(path, tmp_path, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", migrations_up_to(tmp_path, "0006"))
        migrate(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "INSERT INTO concepts (project, round, letter, lever, anon, card_json, idea_ticket,"
            " sketch_ticket, sketch_file, status) VALUES ('prova', 1, 'A', 'forma', 'B', '{}', 'T-0001', '',"
            " 'a.png', 'proposta')"
        )
        connection.execute(
            "INSERT INTO gates (at, project, gate, approved, choice, text, files_json) VALUES"
            " ('2026-11-01T11:00:00+00:00', 'prova', 'concept', 1, 'B', 'La B', '{\"p.pdf\": \"a1b2\"}')"
        )
        connection.execute(
            "INSERT INTO evidence (at, project, file, sha256, check_name, result, signer, ticket_id, proof,"
            " note, inputs_json) VALUES ('2026-11-01T11:00:00+00:00', 'prova', 'segno.svg', 'a1b2',"
            " 'svg_audit', 'PASS', 'qa-inspector', 'T-0002', '', '', '{}')"
        )
        connection.commit()


def test_migration_binds_every_contract_idea_gate_and_proof_into_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One baseline event per ticket binds its state and the sha256 of its contract and opening hashes; one
    per idea, gate and proof binds the row, outside any ticket's history. The events written before stay as
    they were (2.F56-2.F58, ADR-0049)."""
    path = tmp_path / "l.sqlite"
    at_revision_0006(path, tmp_path, monkeypatch)
    columns = f"SELECT {V1_COLUMNS}, version, payload_json FROM events ORDER BY seq"
    before = read(path, columns)
    started = datetime.now(UTC).replace(microsecond=0)

    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", migrations_up_to(tmp_path, "0007"))
        assert migrate(path).revision == "0007"
        ledger = Ledger(path)

    events = read(path, columns)
    assert events[: len(before)] == before
    tickets = ledger.tickets("prova")
    assert [row.id for row in tickets] == [ticket for ticket, *_ in BEFORE_0006]
    bound = [
        (
            ticket.id,
            chain.ticket_binding(
                ticket.status,
                ticket.verdict,
                json.loads(ticket.delivered_json),
                ticket.spec_json,
                ticket.inputs_json,
            ),
        )
        for ticket in tickets
    ]
    bound += [("-", {"concept": row.model_dump()}) for row in ledger.concepts("prova")]
    bound += [("-", {"gate": row.model_dump()}) for row in ledger.gates("prova")]
    bound += [("-", {"evidence": row.model_dump()}) for row in ledger.evidence("prova")]
    added = events[len(before) :]
    assert [(row[1], row[3], row[4], row[5], row[8]) for row in added] == [
        (ticket, "migrate", "baseline", "", 2) for ticket, _ in bound
    ]
    assert [row[9] for row in added] == [chain.canonical(binding) for _, binding in bound]
    assert json.loads(added[len(tickets)][9])["concept"]["status"] == "proposta"
    assert json.loads(added[-2][9])["gate"]["approved"] is True
    (stamp,) = {row[2] for row in added}
    assert started <= datetime.fromisoformat(stamp) <= datetime.now(UTC)
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def at_revision_0007(path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry at revision 0007: the rows of `at_revision_0006` bound by 0007, then two paid calls, two
    projects and a resume record that no event binds, as the code before 0008 wrote them."""
    at_revision_0006(path, tmp_path, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", migrations_up_to(tmp_path, "0007"))
        migrate(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(USAGE)  # a call from before M1.6: its measures stay empty
        connection.execute(
            "INSERT INTO usage (at, project, ticket_id, role, instance, model, input_tokens, output_tokens,"
            " cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cost_usd, stop_reason,"
            " request_id, run, phase, effort, duration_ms, ttft_ms, reasoning_tokens) VALUES"
            " ('2026-11-01T12:00:00+00:00', 'prova', 'T-0002', 'qa-inspector', 'j', 'claude-sonnet-5-5', 900,"
            " 40, 800, 0, 100, 0.0042, 'end_turn', 'req_2', 1, 'qa', 'high', 1300, 210, 12)"
        )
        connection.execute("INSERT INTO projects VALUES ('zeta', 12.5, '', '')")
        connection.execute("INSERT INTO projects VALUES ('prova', 30, 'claude-opus-5-5', 'high')")
        connection.execute(
            "INSERT INTO operations VALUES ('i:t1', 'i', 'view_image', '{}', '2026-11-01T12:00:00+00:00')"
        )
        connection.commit()


def inserts(path: Path) -> list[str]:
    """Every row of every table but Alembic's, as the SQL literal that restores it: the same text is the same
    stored value."""
    with closing(sqlite3.connect(path)) as connection:
        lines = connection.iterdump()
        alembic = 'INSERT INTO "alembic_version"'
        return [line for line in lines if line.startswith("INSERT INTO") and not line.startswith(alembic)]


def test_migration_binds_every_cost_and_budget_into_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One baseline event per paid call, in seq order, and one per project, in name order, binds the row as it
    is, outside any ticket's history; `operations` becomes append-only. No row is rewritten (2.F65,
    ADR-0050)."""
    path = tmp_path / "l.sqlite"
    at_revision_0007(path, tmp_path, monkeypatch)
    columns = f"SELECT {V1_COLUMNS}, version, payload_json FROM events ORDER BY seq"
    before, rows = read(path, columns), inserts(path)
    started = datetime.now(UTC).replace(microsecond=0)

    assert migrate(path).revision == "0008"

    after = inserts(path)
    assert [line for line in rows if line not in after] == []
    new = [line for line in after if line not in rows]
    assert [line.split(" VALUES")[0] for line in new] == ['INSERT INTO "events"'] * 4
    events = read(path, columns)
    assert events[: len(before)] == before
    ledger = Ledger(path)
    bound = [{"usage": row.model_dump()} for row in ledger.usage("prova")]
    bound += [{"project": row.model_dump()} for row in map(ledger.project, ("prova", "zeta")) if row]
    added = events[len(before) :]
    assert [(row[1], row[3], row[4], row[5], row[8]) for row in added] == [
        ("-", "migrate", "baseline", "", 2)
    ] * 4
    assert [row[9] for row in added] == [chain.canonical(binding) for binding in bound]
    assert json.loads(added[0][9])["usage"]["run"] is None
    assert json.loads(added[2][9])["project"]["budget_usd"] == 30.0
    (stamp,) = {row[2] for row in added}
    assert started <= datetime.fromisoformat(stamp) <= datetime.now(UTC)
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []
    triggers = read(path, "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'operations'")
    assert sorted(triggers) == [("operations_no_delete",), ("operations_no_update",)]
