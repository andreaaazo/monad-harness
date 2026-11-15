"""The read slice reads the registry read-only, and its use cases build the views from it."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from agency.contracts.layout import DataLayout
from agency.contracts.ledger import EvidenceEntry
from agency.contracts.run import Fingerprint, RunCommand
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.insights import application
from agency.insights.adapters.ledger import ReadOnlyLedger
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import JsonlTranscripts
from agency.insights.domain import (
    Lifecycle,
)
from agency.ledger import Ledger
from agency.ledger.schema import head
from support.insights import FakeRegistry, digest, filled_registry, span


def test_the_registry_reader_reads_and_cannot_write(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    filled_registry(path).engine.dispose()
    before = digest(path)
    registry = ReadOnlyLedger(path)

    (row,) = registry.read().usage

    assert (row.project, row.phase, row.duration_ms) == ("merlo4", "director-plan", 4100)
    assert registry.revision() == head()
    with closing(registry.connect()) as connection:
        assert connection.execute("PRAGMA query_only").fetchone() == (1,)
        connection.execute(
            "PRAGMA query_only = OFF"
        )  # even with one defence removed, the other holds: mode=ro
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM projects")
    assert digest(path) == before


def test_ticket_events_are_the_opening_and_every_transition_the_engine_knows() -> None:
    """Proofs have their own table: in a ticket's history, the opening and the transitions count."""
    assert {item.value for item in Lifecycle} == {"open"} | {action.value for action in Action}


def proposal(ledger: Ledger) -> str:
    spec = TicketSpec(
        title="Proposta X r1",
        request="Il segno",
        type=TicketType.PROPOSAL,
        sender="design-director",
        assignee="identity-designer",
        outputs=["segno.svg"],
        checks={"*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
        prompt="proposer",
    )
    return ledger.open(spec, "merlo4")


def evidence(ticket_id: str, check: str, result: str, note: str) -> EvidenceEntry:
    return EvidenceEntry(
        at="2026-11-02T10:00:00+00:00",
        project="merlo4",
        file="segno.svg",
        sha256="a" * 64,
        check_name=check,
        result=result,
        signer="tool",
        ticket_id=ticket_id,
        proof="proofs/segno.png",
        note=note,
    )


def test_the_registry_reader_reads_the_life_of_tickets_and_why_they_went_back(tmp_path: Path) -> None:
    """The reason is read only for a step back: it is what says where the work goes wrong. The words of a
    delivery or of an opening stay in the registry."""
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ticket_id = proposal(ledger)
    ledger.apply(ticket_id, Action.DELIVER, "identity-designer", note="Le parole del designer")
    ledger.apply(ticket_id, Action.REWORK, "design-director", note="La coda è troppo sottile a 16 px")
    ledger.add_evidence(evidence(ticket_id, "svg_audit", "PASS", "ok"))
    ledger.engine.dispose()

    events = ReadOnlyLedger(tmp_path / "ledger.sqlite").read().events

    assert [
        (event.project, event.ticket_id, event.actor, event.action, event.reason) for event in events
    ] == [
        ("merlo4", ticket_id, "design-director", Lifecycle.OPEN, None),
        ("merlo4", ticket_id, "identity-designer", Lifecycle.DELIVER, None),
        ("merlo4", ticket_id, "design-director", Lifecycle.REWORK, "La coda è troppo sottile a 16 px"),
    ]


def fingerprint(**extra: object) -> Fingerprint:
    base: dict[str, object] = {
        "model": "",
        "effort": "high",
        "explorer_effort": "high",
        "proposal_effort": "high",
        "explorers": 5,
        "max_parallel": 5,
        "prompts": {"prompts/roles/critic.md": "a" * 64},
        "registry": {"registry/roles.json": "b" * 64},
        "code": {"src/agency/cli.py": "c" * 64},
        "lock": "d" * 64,
        "python": "3.13.1",
        "tools": {"vectorcraft-cli": "vectorcraft 1.0"},
    }
    return Fingerprint.model_validate(base | extra)


def test_the_registry_reader_reads_every_execution_with_its_fingerprint(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    first = ledger.record_run("merlo4", RunCommand.RUN, fingerprint())
    second = ledger.record_run("merlo4", RunCommand.DECIDE, fingerprint(explorers=3))
    ledger.engine.dispose()

    runs = ReadOnlyLedger(tmp_path / "ledger.sqlite").read().runs

    assert [(run.seq, run.project, run.command, run.digest) for run in runs] == [
        (first, "merlo4", "run", fingerprint().digest()),
        (second, "merlo4", "decide", fingerprint(explorers=3).digest()),
    ]
    assert Fingerprint.model_validate_json(runs[1].fingerprint_json) == fingerprint(explorers=3)


def test_the_registry_reader_reads_every_check_with_its_result_and_reason(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ticket_id = proposal(ledger)
    ledger.add_evidence(evidence(ticket_id, "svg_audit", "FAIL", "3 nodi sottotracciati"))
    ledger.add_evidence(evidence(ticket_id, "svg_audit", "PASS", ""))
    ledger.engine.dispose()

    checks = ReadOnlyLedger(tmp_path / "ledger.sqlite").read().checks

    assert [
        (item.project, item.ticket_id, item.file, item.check_name, item.result, item.reason)
        for item in checks
    ] == [
        ("merlo4", ticket_id, "segno.svg", "svg_audit", "FAIL", "3 nodi sottotracciati"),
        ("merlo4", ticket_id, "segno.svg", "svg_audit", "PASS", ""),
    ]
    assert checks[0].signer == "tool"


def test_the_registry_reader_works_while_the_engine_is_writing(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = filled_registry(path)
    writing, done = threading.Event(), threading.Event()

    def engine() -> None:
        with ledger.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")  # the engine holds the write lock
            writing.set()
            done.wait(timeout=10)
            connection.rollback()

    thread = threading.Thread(target=engine)
    thread.start()
    assert writing.wait(timeout=10), "the engine never took the write lock: nothing was read while it wrote"
    try:
        assert len(ReadOnlyLedger(path).read().usage) == 1
    finally:
        done.set()
        thread.join()


def test_a_missing_registry_is_explained(tmp_path: Path) -> None:
    with pytest.raises(application.LedgerNotReadable, match="non esiste"):
        ReadOnlyLedger(tmp_path / "ledger.sqlite").revision()


def test_a_registry_that_cannot_be_opened_is_explained_not_crashed(tmp_path: Path) -> None:
    """A WAL registry closed by the engine has no -shm file: the reader must create it. In a folder that is
    not writable SQLite cannot open it, and the dashboard reports an unreadable registry, not a 500."""
    folder = tmp_path / "dati"
    folder.mkdir()
    filled_registry(folder / "ledger.sqlite").engine.dispose()
    assert not (folder / "ledger.sqlite-shm").exists()
    folder.chmod(0o555)
    try:
        registry = ReadOnlyLedger(folder / "ledger.sqlite")
        with pytest.raises(application.LedgerNotReadable, match="non si apre"):
            registry.revision()
        with pytest.raises(application.LedgerNotReadable, match="non si apre"):
            registry.read()
    finally:
        folder.chmod(0o755)


# The use cases


def test_insights_reads_exactly_the_revision_the_engine_writes() -> None:
    assert head() == application.READS_REVISION


@pytest.mark.parametrize(
    ("revision", "advice"), [(None, "agency migrate"), ("0001", "agency migrate"), ("9999", "insights")]
)
def test_rebuild_refuses_a_registry_it_does_not_know(
    tmp_path: Path, revision: str | None, advice: str
) -> None:
    projection = SqliteProjection(tmp_path / "insights.sqlite")
    with pytest.raises(application.LedgerNotReadable, match=advice):
        application.rebuild(
            FakeRegistry(revision),
            JsonlTraces(tmp_path / "t.jsonl"),
            JsonlTranscripts(DataLayout(tmp_path)),
            projection,
            "2026-11-02",
        )
    assert not (tmp_path / "insights.sqlite").exists()


def test_rebuild_projects_every_call_and_says_where_measures_came_from(tmp_path: Path) -> None:
    traces = tmp_path / "traces.jsonl"
    traces.write_text(span("anthropic.messages.create", "req_1") + "\n", encoding="utf-8")
    projection = SqliteProjection(tmp_path / "insights.sqlite")

    built = application.rebuild(
        FakeRegistry(application.READS_REVISION),
        JsonlTraces(traces),
        JsonlTranscripts(DataLayout(tmp_path)),
        projection,
        "2026-11-02T11:00:00+00:00",
    )

    assert (built.calls, built.from_registry, built.from_traces, built.unmeasured) == (2, 1, 1, 0)
    assert (built.phases_recorded, built.phases_derived) == (1, 1)
    assert [call.seq for call in projection.calls()] == [1, 2]
    assert projection.provenance() == built
