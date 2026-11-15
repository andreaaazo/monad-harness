"""The read slice's projection, kept in step with the registry, and the command that rebuilds it."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlmodel import Session

from agency.agents.transcript import Transcript
from agency.contracts.layout import DataLayout
from agency.contracts.project import ProjectName
from agency.contracts.ticket import TicketSpec, TicketType
from agency.entrypoints import cli
from agency.insights import application
from agency.insights.adapters.ledger import ReadOnlyLedger
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import JsonlTranscripts
from agency.insights.domain import (
    Call,
    CheckRecord,
    ConceptRecord,
    EventRecord,
    GateRecord,
    JudgmentRecord,
    Lifecycle,
    Projected,
    ProjectRecord,
    Provenance,
    RunRecord,
    TicketRecord,
    ToolCallRecord,
)
from agency.ledger import Ledger
from agency.ledger.models import TicketRow
from agency.ledger.schema import head
from support.insights import FakeRegistry, answer, call, digest, event, filled_registry, results, turn, use


def only(calls: list[Call]) -> Projected:
    return Projected(
        calls=calls,
        projects=[],
        tickets=[],
        gates=[],
        concepts=[],
        judgments=[],
        events=[],
        checks=[],
        tool_calls=[],
        runs=[],
    )


def rebuilt(calls: int) -> Provenance:
    return Provenance(
        built_at="2026-11-02",
        sources=[],
        registry_revision=application.READS_REVISION,
        calls=calls,
        from_registry=0,
        from_traces=0,
        unmeasured=calls,
        phases_recorded=0,
        phases_derived=calls,
        unreadable_trace_lines=0,
        unreadable_transcript_lines=0,
    )


def test_projection_columns_come_from_the_model(tmp_path: Path) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    projection.replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(tmp_path / "insights.sqlite")) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(calls)")]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert columns == list(Call.model_fields)
    assert version == SqliteProjection.SCHEMA


def test_projection_reads_back_exactly_what_it_wrote_and_filters_by_project(tmp_path: Path) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    written = [call(1), call(2, "merlo"), call(3)]
    projection.replace(only(written), rebuilt(3))
    assert projection.calls() == written
    assert [item.seq for item in projection.calls("merlo3")] == [1, 3]


def test_projection_keeps_the_events_of_each_project(tmp_path: Path) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    events = [
        event(1, "merlo3", Lifecycle.OPEN),
        event(2, "merlo", Lifecycle.OPEN),
        event(3, "merlo3", Lifecycle.BLOCK),
    ]
    projection.replace(only([]).model_copy(update={"events": events}), rebuilt(0))
    assert projection.project("merlo3").events == [events[0], events[2]]


def test_a_reader_never_sees_a_half_written_projection(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    projection = SqliteProjection(path)
    projection.replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as reader:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM calls").fetchone()[0] == 1
        projection.replace(only([call(1), call(2)]), rebuilt(2))
        assert reader.execute("SELECT count(*) FROM calls").fetchone()[0] == 1  # its version stays whole
    assert len(projection.calls()) == 2
    assert [item.name for item in tmp_path.iterdir()] == ["insights.sqlite"]


def test_a_failed_rebuild_leaves_the_previous_projection(tmp_path: Path) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    projection.replace(only([call(1)]), rebuilt(1))
    with pytest.raises(sqlite3.IntegrityError):
        projection.replace(only([call(1), call(1)]), rebuilt(2))  # two calls with the same number
    assert [item.seq for item in projection.calls()] == [1]
    assert [item.name for item in tmp_path.iterdir()] == ["insights.sqlite"]


def test_a_change_to_what_the_projection_stores_changes_its_schema_number() -> None:
    """If a stored model changes and the schema number does not, an old projection is misread instead of
    rebuilt.

    The fingerprint covers the stored shape only: a docstring is no column. When this test fails, raise
    SqliteProjection.SCHEMA and update the fingerprint here.
    """
    stored = (
        Call,
        ProjectRecord,
        TicketRecord,
        GateRecord,
        ConceptRecord,
        JudgmentRecord,
        EventRecord,
        CheckRecord,
        ToolCallRecord,
        RunRecord,
        Provenance,
    )
    shape = json.dumps([_without_descriptions(model.model_json_schema()) for model in stored], sort_keys=True)
    assert (SqliteProjection.SCHEMA, hashlib.sha256(shape.encode()).hexdigest()[:16]) == (
        6,
        "2f88b9215fa57f05",
    )


def _without_descriptions(schema: object) -> object:
    """The JSON schema without the docstrings and field descriptions it carries as `description` texts.

    Only text values go: a stored field named `description` is part of the shape, and its schema is an object.
    """
    if isinstance(schema, dict):
        return {
            key: _without_descriptions(value)
            for key, value in schema.items()
            if not (key == "description" and isinstance(value, str))
        }
    if isinstance(schema, list):
        return [_without_descriptions(value) for value in schema]
    return schema


def test_a_projection_of_the_previous_schema_is_rebuilt_not_misread(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    SqliteProjection(path).replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            'UPDATE meta SET value = \'{"built_at": "ieri"}\''
        )  # the provenance of an old schema
        connection.execute(f"PRAGMA user_version = {SqliteProjection.SCHEMA - 1}")
        connection.commit()
    built = application.current(
        FakeRegistry(application.READS_REVISION),
        JsonlTraces(tmp_path / "t.jsonl"),
        JsonlTranscripts(DataLayout(tmp_path)),
        SqliteProjection(path),
        "oggi",
    )
    assert built.built_at == "oggi"


def test_a_transcript_that_grows_makes_the_projection_old(tmp_path: Path) -> None:
    """A working instance writes its transcript: on the next read, the projection is rebuilt."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo3"), "T-0002-a1"))
    transcript.append(turn(use("u1", "render")))
    registry, traces = FakeRegistry(application.READS_REVISION), JsonlTraces(tmp_path / "t.jsonl")
    projection, transcripts = (
        SqliteProjection(tmp_path / "insights.sqlite"),
        JsonlTranscripts(layout),
    )
    assert application.current(registry, traces, transcripts, projection, "prima").built_at == "prima"
    assert application.current(registry, traces, transcripts, projection, "poi").built_at == "prima"

    transcript.append(results(answer("u1", "render non disponibile", error=True)))

    assert application.current(registry, traces, transcripts, projection, "dopo").built_at == "dopo"
    assert [item.refusal for item in projection.project("merlo3").tool_calls] == ["render non disponibile"]


def test_an_old_projection_schema_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    SqliteProjection(path).replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    with pytest.raises(application.ProjectionOutdated, match="agency insights"):
        SqliteProjection(path).calls()


# The command


def test_agency_insights_rebuilds_and_reports_where_data_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    filled_registry(tmp_path / "ledger.sqlite").engine.dispose()
    before = digest(tmp_path / "ledger.sqlite")

    assert cli.main(["insights"]) == 0

    out = capsys.readouterr().out
    assert f"revisione {head()}" in out and "1 chiamata" in out
    assert "misure: 1 dal registro, 0 dalle tracce, 0 non misurate" in out
    assert digest(tmp_path / "ledger.sqlite") == before
    assert len(SqliteProjection(tmp_path / "insights.sqlite").calls()) == 1


def test_agency_insights_on_an_outdated_registry_says_what_to_do(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    with closing(sqlite3.connect(tmp_path / "ledger.sqlite")) as connection:
        connection.execute("CREATE TABLE usage (seq INTEGER)")
    assert cli.main(["insights"]) == 1
    assert "agency migrate" in capsys.readouterr().out
    assert not (tmp_path / "insights.sqlite").exists()


def test_ticket_10000_is_listed_after_ticket_9999_by_the_registry_reader_and_the_projection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = Ledger(path)
    with Session(ledger.engine) as session:
        session.add_all(
            TicketRow(
                id=id_,
                project="merlo4",
                spec_json=TicketSpec(
                    title=id_, request="x", type=TicketType.DISPUTE, sender="a", assignee="b"
                ).model_dump_json(),
                status="open",
                created_at="2026-11-02T09:00:00+00:00",
            )
            for id_ in ("T-9999", "T-10000")
        )
        session.commit()
    ledger.engine.dispose()

    snapshot = ReadOnlyLedger(path).read()
    assert list(snapshot.tickets) == ["T-9999", "T-10000"]

    projection = SqliteProjection(tmp_path / "insights.sqlite")
    projection.replace(only([]).model_copy(update={"tickets": list(snapshot.tickets.values())}), rebuilt(0))
    assert [item.id for item in projection.project("merlo4").tickets] == ["T-9999", "T-10000"]
