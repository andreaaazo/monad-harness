"""La slice di lettura: proietta registro e tracce senza mai scrivere il registro (M1.6, punto 9)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from agency import cli
from agency.contracts import phase
from agency.insights import application
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.registry import ReadOnlyRegistry
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.domain import (
    Call,
    ConceptRecord,
    GateRecord,
    JudgmentRecord,
    Measures,
    PhaseSource,
    Projected,
    ProjectRecord,
    Provenance,
    SourceStamp,
    TicketRecord,
    TraceMeasure,
    UsageRecord,
    derive_phase,
    project_calls,
)
from agency.insights.ports import RegistrySnapshot
from agency.ledger import Ledger
from agency.ledger.models import UsageRow
from agency.ledger.schema import head


def usage(**extra: object) -> UsageRecord:
    base: dict[str, object] = {
        "seq": 1,
        "at": "2026-11-02T10:00:00+00:00",
        "project": "merlo3",
        "ticket_id": "T-0001",
        "role": "design-director",
        "instance": "T-0001-a1-plan",
        "model": "claude-opus-5-5",
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_usd": 0.01,
        "stop_reason": "tool_use",
        "request_id": "req_1",
        "run": None,
        "phase": None,
        "effort": None,
        "duration_ms": None,
        "ttft_ms": None,
        "reasoning_tokens": None,
    }
    return UsageRecord.model_validate(base | extra)


def ticket(id_: str, type_: str, assignee: str, prompt: str = "") -> TicketRecord:
    return TicketRecord(
        id=id_,
        project="merlo3",
        type=type_,
        assignee=assignee,
        prompt=prompt,
        title=f"Ticket {id_}",
        status="accepted",
        verdict=None,
        created_at="2026-11-02T09:00:00+00:00",
    )


TICKETS = {
    "T-0001": ticket("T-0001", "consegna", "design-director"),
    "T-0002": ticket("T-0002", "schizzo", "direction-a", "explorer"),
    "T-0009": ticket("T-0009", "revisione", "critic"),
}
TRACE = TraceMeasure(request_id="req_1", duration_ms=8200, ttft_ms=1400, effort="high", reasoning_tokens=310)


# Le regole: la fase


@pytest.mark.parametrize(
    ("instance", "ticket", "role", "expected"),
    [
        ("T-0001-a1-plan", "T-0001", "design-director", "director-plan"),
        ("T-0001-a2-select", "T-0001", "design-director", "director-select"),
        ("T-0001-a1-present", "T-0001", "design-director", "director-present"),
        ("T-0001-a3", "T-0001", "design-director", "design-director"),
        ("T-0002-a1", "T-0002", "direction-a", "explorer"),
        ("T-0009-a1", "T-0009", "critic", "critic"),
        ("T-0099-a1", "T-0099", "critic", "critic"),  # un ticket che il registro non ha: resta il ruolo
    ],
)
def test_phase_of_an_old_call_is_derived_with_the_rule_the_engine_uses(
    instance: str, ticket: str, role: str, expected: str
) -> None:
    assert derive_phase(usage(instance=instance, ticket_id=ticket, role=role), TICKETS) == expected


def test_a_recorded_phase_wins_over_the_derived_one() -> None:
    """Quella registrata è la verità di allora, anche se la regola di oggi direbbe altro."""
    (call,) = project_calls([usage(phase="explorer-idea")], TICKETS, {})
    assert (call.phase, call.phase_source) == ("explorer-idea", PhaseSource.RECORDED)
    (old,) = project_calls([usage()], TICKETS, {})
    assert (old.phase, old.phase_source) == ("director-plan", PhaseSource.DERIVED)


def test_instance_names_are_written_and_read_by_one_rule() -> None:
    for mode in ("", *phase.MODES):
        assert phase.mode_of(phase.instance("T-0042", 3, mode)) == mode
    assert phase.mode_of("i1") == ""  # un nome di prova non è un'istanza del motore


# Le regole: le misure


def test_a_new_call_keeps_its_own_measures_even_if_a_trace_exists() -> None:
    new = usage(effort="medium", duration_ms=5000, ttft_ms=None, reasoning_tokens=12)
    (call,) = project_calls([new], TICKETS, {"req_1": TRACE})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == ("medium", 5000, None, 12, Measures.REGISTRY)


def test_an_old_call_takes_its_measures_from_the_trace() -> None:
    (call,) = project_calls([usage()], TICKETS, {"req_1": TRACE})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == ("high", 8200, 1400, 310, Measures.TRACES)


def test_an_old_call_without_trace_says_it_was_not_measured() -> None:
    (call,) = project_calls([usage()], TICKETS, {})
    measured = (call.effort, call.duration_ms, call.ttft_ms, call.reasoning_tokens, call.measures)
    assert measured == (None, None, None, None, Measures.MISSING)


def test_a_call_keeps_cost_tokens_and_the_type_of_its_ticket() -> None:
    (call,) = project_calls(
        [usage(ticket_id="T-0002", instance="T-0002-a1", role="direction-a")], TICKETS, {}
    )
    assert (call.ticket_type, call.cost_usd, call.input_tokens, call.request_id) == (
        "schizzo",
        0.01,
        100,
        "req_1",
    )
    (orphan,) = project_calls([usage(ticket_id="T-0099")], TICKETS, {})
    assert orphan.ticket_type == ""


# Le tracce


def span(name: str, request_id: str, **attributes: object) -> str:
    record = {
        "name": name,
        "start": 1_000_000_000,
        "end": 1_000_000_000 + 8_200_000_000,
        "trace": "abc",
        "attributes": {"anthropic.request.id": request_id} | attributes,
    }
    return json.dumps(record)


def test_traces_give_duration_ttft_effort_and_reasoning_by_request(tmp_path: Path) -> None:
    lines = [
        span(
            "anthropic.messages.create",
            "req_1",
            **{
                "gen_ai.response.time_to_first_chunk": 1.4004,
                "gen_ai.request.reasoning.level": "high",
                "gen_ai.usage.reasoning.output_tokens": 310,
            },
        ),
        span("model.call", "req_9"),  # le tracce nostre non hanno le misure dell'SDK
        '{"name": "anthropic.messages.create", "start": 1, ',  # riga tagliata da un processo ucciso
        span("anthropic.messages.create", "req_2"),
    ]
    path = tmp_path / "traces.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    reading = JsonlTraces(path).read()

    assert reading.measures["req_1"] == TRACE
    assert reading.measures["req_2"] == TraceMeasure(
        request_id="req_2", duration_ms=8200, ttft_ms=None, effort=None, reasoning_tokens=None
    )
    assert set(reading.measures) == {"req_1", "req_2"}
    assert reading.unreadable == 1


def test_missing_traces_are_not_an_error(tmp_path: Path) -> None:
    reading = JsonlTraces(tmp_path / "traces.jsonl").read()
    assert (reading.measures, reading.unreadable) == ({}, 0)


# Il registro, in sola lettura


def filled_registry(path: Path) -> Ledger:
    ledger = Ledger(path)
    ledger.record_usage(
        UsageRow(
            at="2026-11-02T10:00:00+00:00",
            project="merlo4",
            ticket_id="T-0001",
            role="design-director",
            instance="T-0001-a1-plan",
            model="claude-opus-5-5",
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.01,
            stop_reason="tool_use",
            request_id="req_1",
            phase="director-plan",
            effort="high",
            duration_ms=4100,
        )
    )
    return ledger


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_registry_reader_reads_and_cannot_write(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    filled_registry(path).engine.dispose()
    before = digest(path)
    registry = ReadOnlyRegistry(path)

    (row,) = registry.read().usage

    assert (row.project, row.phase, row.duration_ms) == ("merlo4", "director-plan", 4100)
    assert registry.revision() == head()
    with closing(registry.connect()) as connection:
        assert connection.execute("PRAGMA query_only").fetchone() == (1,)
        connection.execute("PRAGMA query_only = OFF")  # anche togliendo una difesa, resta l'altra: mode=ro
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM projects")
    assert digest(path) == before


def test_the_registry_reader_works_while_the_engine_is_writing(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = filled_registry(path)
    writing, done = threading.Event(), threading.Event()

    def engine() -> None:
        with ledger.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")  # il motore tiene il lucchetto di scrittura
            writing.set()
            done.wait(timeout=10)
            connection.rollback()

    thread = threading.Thread(target=engine)
    thread.start()
    writing.wait(timeout=10)
    try:
        assert len(ReadOnlyRegistry(path).read().usage) == 1
    finally:
        done.set()
        thread.join()


def test_a_missing_registry_is_explained(tmp_path: Path) -> None:
    with pytest.raises(application.RegistryNotReadable, match="non esiste"):
        ReadOnlyRegistry(tmp_path / "ledger.sqlite").revision()


# Il caso d'uso


def test_insights_reads_exactly_the_revision_the_engine_writes() -> None:
    assert head() == application.READS_REVISION


class FakeRegistry:
    def __init__(self, revision: str | None) -> None:
        self._revision = revision

    def stamp(self) -> list[SourceStamp]:
        return [SourceStamp(name="ledger.sqlite", size=1, modified_ns=1)]

    def revision(self) -> str | None:
        return self._revision

    def read(self) -> RegistrySnapshot:
        calls = [usage(), usage(seq=2, request_id="req_2", phase="director-plan", duration_ms=10)]
        return RegistrySnapshot(
            usage=calls, tickets=TICKETS, projects=[], gates=[], concepts=[], judgments=[]
        )


@pytest.mark.parametrize(
    ("revision", "advice"), [(None, "agency migrate"), ("0001", "agency migrate"), ("9999", "insights")]
)
def test_rebuild_refuses_a_registry_it_does_not_know(
    tmp_path: Path, revision: str | None, advice: str
) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    with pytest.raises(application.RegistryNotReadable, match=advice):
        application.rebuild(
            FakeRegistry(revision), JsonlTraces(tmp_path / "t.jsonl"), projection, "2026-11-02"
        )
    assert not (tmp_path / "insights.sqlite").exists()


def test_rebuild_projects_every_call_and_says_where_measures_came_from(tmp_path: Path) -> None:
    traces = tmp_path / "traces.jsonl"
    traces.write_text(span("anthropic.messages.create", "req_1") + "\n", encoding="utf-8")
    projection = SqliteProjection(tmp_path / "insights.sqlite")

    built = application.rebuild(
        FakeRegistry(application.READS_REVISION), JsonlTraces(traces), projection, "2026-11-02T11:00:00+00:00"
    )

    assert (built.calls, built.from_registry, built.from_traces, built.unmeasured) == (2, 1, 1, 0)
    assert (built.phases_recorded, built.phases_derived) == (1, 1)
    assert [call.seq for call in projection.calls()] == [1, 2]
    assert projection.provenance() == built


# La proiezione


def call(seq: int, project: str = "merlo3") -> Call:
    (projected,) = project_calls([usage(seq=seq, project=project, request_id=f"req_{seq}")], TICKETS, {})
    return projected


def only(calls: list[Call]) -> Projected:
    return Projected(calls=calls, projects=[], tickets=[], gates=[], concepts=[], judgments=[])


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


def test_a_reader_never_sees_a_half_written_projection(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    projection = SqliteProjection(path)
    projection.replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as reader:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM calls").fetchone()[0] == 1
        projection.replace(only([call(1), call(2)]), rebuilt(2))
        assert reader.execute("SELECT count(*) FROM calls").fetchone()[0] == 1  # la sua versione resta intera
    assert len(projection.calls()) == 2
    assert [item.name for item in tmp_path.iterdir()] == ["insights.sqlite"]


def test_a_failed_rebuild_leaves_the_previous_projection(tmp_path: Path) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    projection.replace(only([call(1)]), rebuilt(1))
    with pytest.raises(sqlite3.IntegrityError):
        projection.replace(only([call(1), call(1)]), rebuilt(2))  # due chiamate con lo stesso numero
    assert [item.seq for item in projection.calls()] == [1]
    assert [item.name for item in tmp_path.iterdir()] == ["insights.sqlite"]


def test_a_change_to_what_the_projection_stores_changes_its_schema_number() -> None:
    """Se un modello salvato cambia e lo schema no, una proiezione vecchia si legge male invece di rifarsi.

    Quando questo test fallisce: si alza SqliteProjection.SCHEMA e si aggiorna qui l'impronta.
    """
    stored = (Call, ProjectRecord, TicketRecord, GateRecord, ConceptRecord, JudgmentRecord, Provenance)
    shape = json.dumps([model.model_json_schema() for model in stored], sort_keys=True)
    assert (SqliteProjection.SCHEMA, hashlib.sha256(shape.encode()).hexdigest()[:16]) == (
        3,
        "09acddcb4981fe8a",
    )


def test_a_projection_of_the_previous_schema_is_rebuilt_not_misread(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    SqliteProjection(path).replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            'UPDATE meta SET value = \'{"built_at": "ieri"}\''
        )  # la provenienza di uno schema vecchio
        connection.execute(f"PRAGMA user_version = {SqliteProjection.SCHEMA - 1}")
        connection.commit()
    built = application.current(
        FakeRegistry(application.READS_REVISION),
        JsonlTraces(tmp_path / "t.jsonl"),
        SqliteProjection(path),
        "oggi",
    )
    assert built.built_at == "oggi"


def test_an_old_projection_schema_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "insights.sqlite"
    SqliteProjection(path).replace(only([call(1)]), rebuilt(1))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    with pytest.raises(application.ProjectionOutdated, match="agency insights"):
        SqliteProjection(path).calls()


# Il comando


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
