"""The read slice: it projects the registry, the traces and the transcripts without ever writing the
registry (M1.6, item 9).
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest
from sqlmodel import Session

from agency import cli
from agency.agents.transcript import Transcript
from agency.contracts import phase
from agency.contracts.layout import DataLayout
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import ProjectName
from agency.contracts.run import Fingerprint, RunCommand
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
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
    Measures,
    PhaseSource,
    Projected,
    ProjectRecord,
    Provenance,
    RunRecord,
    SourceStamp,
    TicketRecord,
    ToolCallRecord,
    TraceMeasure,
    UsageRecord,
    derive_phase,
    project_calls,
)
from agency.insights.ports import LedgerSnapshot
from agency.ledger import Ledger
from agency.ledger.models import EvidenceRow, TicketRow, UsageRow
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


# The rules: the phase


@pytest.mark.parametrize(
    ("instance", "ticket", "role", "expected"),
    [
        ("T-0001-a1-plan", "T-0001", "design-director", "director-plan"),
        ("T-0001-a2-select", "T-0001", "design-director", "director-select"),
        ("T-0001-a1-present", "T-0001", "design-director", "director-present"),
        ("T-0001-a3", "T-0001", "design-director", "design-director"),
        ("T-0002-a1", "T-0002", "direction-a", "explorer"),
        ("T-0009-a1", "T-0009", "critic", "critic"),
        ("T-0099-a1", "T-0099", "critic", "critic"),  # a ticket the registry lacks: the role stays
    ],
)
def test_phase_of_an_old_call_is_derived_with_the_rule_the_engine_uses(
    instance: str, ticket: str, role: str, expected: str
) -> None:
    assert derive_phase(usage(instance=instance, ticket_id=ticket, role=role), TICKETS) == expected


def test_a_recorded_phase_wins_over_the_derived_one() -> None:
    """The recorded phase is the truth of its time, even if today's rule would say otherwise."""
    (call,) = project_calls([usage(phase="explorer-idea")], TICKETS, {})
    assert (call.phase, call.phase_source) == ("explorer-idea", PhaseSource.RECORDED)
    (old,) = project_calls([usage()], TICKETS, {})
    assert (old.phase, old.phase_source) == ("director-plan", PhaseSource.DERIVED)


def test_instance_names_are_written_and_read_by_one_rule() -> None:
    for mode in ("", *phase.MODES):
        assert phase.mode_of(phase.instance("T-0042", 3, mode)) == mode
    assert phase.mode_of("i1") == ""  # a test name is not an engine instance


# The rules: the measures


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


# The traces


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
        span("model.call", "req_9"),  # our own traces lack the SDK's measures
        '{"name": "anthropic.messages.create", "start": 1, ',  # a line cut short by a killed process
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


def test_a_stray_non_utf8_byte_costs_one_line_not_the_whole_trace_file(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    path.write_bytes(
        span("anthropic.messages.create", "req_1").encode()
        + b"\n"
        + b'{"name": "\xff"}\n'
        + span("anthropic.messages.create", "req_2").encode()
        + b"\n"
    )

    reading = JsonlTraces(path).read()

    assert set(reading.measures) == {"req_1", "req_2"}
    assert reading.unreadable == 1


def test_a_broken_stream_is_not_a_complete_answer() -> None:
    from agency.insights import behaviour

    stops = behaviour._stops([call(1), call(2)])
    assert [(stop.reason, stop.complete) for stop in stops] == [("tool_use", True)]
    (projected,) = project_calls(
        [usage(seq=3, request_id="req_3", stop_reason="malformed_stream")], TICKETS, {}
    )
    (broken,) = behaviour._stops([projected])
    assert (broken.reason, broken.complete) == ("malformed_stream", False)


def test_missing_traces_are_not_an_error(tmp_path: Path) -> None:
    reading = JsonlTraces(tmp_path / "traces.jsonl").read()
    assert (reading.measures, reading.unreadable) == ({}, 0)


# The transcripts: from each, only the tools used and their refusals


def turn(*blocks: dict) -> dict:
    return {"role": "assistant", "content": list(blocks)}


def results(*blocks: dict) -> dict:
    return {"role": "user", "content": list(blocks)}


def use(id_: str, name: str) -> dict:
    return {"type": "tool_use", "id": id_, "name": name, "input": {"path": "segno.svg"}}


def answer(id_: str, text: str, *, error: bool = False) -> dict:
    block: dict[str, object] = {"type": "tool_result", "tool_use_id": id_, "content": text}
    return block | {"is_error": True} if error else block


def test_transcripts_give_every_tool_call_and_the_refusals_with_their_words(tmp_path: Path) -> None:
    """The engine writes the transcript and insights reads it through the same path: DataLayout."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append({"role": "user", "content": "Il brief del cliente"})
    transcript.append(
        turn({"type": "text", "text": "Guardo il file"}, use("u1", "view_image"), use("u2", "deliver"))
    )
    content = [{"type": "text", "text": "consegna rifiutata:"}, {"type": "text", "text": "manca la prova"}]
    transcript.append(
        results(
            answer("u1", "ok"),
            {"type": "tool_result", "tool_use_id": "u2", "is_error": True, "content": content},
        )
    )
    transcript.append(turn(use("u3", "deliver")))
    transcript.append(results(answer("u3", '{"ok": true}')))

    reading = JsonlTranscripts(layout).read()

    assert [(item.project, item.instance, item.turn, item.tool, item.refusal) for item in reading.calls] == [
        ("merlo4", "T-0002-a1", 1, "view_image", None),
        ("merlo4", "T-0002-a1", 1, "deliver", "consegna rifiutata:\nmanca la prova"),
        ("merlo4", "T-0002-a1", 2, "deliver", None),
    ]
    assert [item.seq for item in reading.calls] == [1, 2, 3]
    assert reading.unreadable == 0


def test_a_half_written_line_is_counted_and_skipped_and_the_stamp_names_each_transcript(
    tmp_path: Path,
) -> None:
    layout = DataLayout(tmp_path)
    Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1")).append(turn(use("u1", "render")))
    with layout.transcript(ProjectName("merlo4"), "T-0002-a1").open("a", encoding="utf-8") as handle:
        handle.write('{"message": {"role": "user", "cont')  # the engine is writing

    transcripts = JsonlTranscripts(layout)

    reading = transcripts.read()
    assert ([item.tool for item in reading.calls], reading.unreadable) == (["render"], 1)
    assert [item.name for item in transcripts.stamp()] == ["runs/merlo4/T-0002-a1.jsonl"]


def test_a_line_torn_inside_a_utf8_character_counts_as_unreadable(tmp_path: Path) -> None:
    """The engine writes Italian unescaped, so a line can stop after the first byte of `è`."""
    layout = DataLayout(tmp_path)
    path = layout.transcript(ProjectName("merlo4"), "T-0002-a1")
    Transcript(path).append(turn(use("u1", "render")))
    with path.open("ab") as handle:
        handle.write(b'{"a":"\xc3')  # the engine was writing "è"
    transcripts = JsonlTranscripts(layout)

    reading = transcripts.read()
    assert reading.unreadable == 1
    assert [call.tool for call in reading.calls] == ["render"]
    record = transcripts.transcript("merlo4", "T-0002-a1")
    assert record is not None
    assert record.unreadable == 1
    assert [tool.name for item in record.turns for tool in item.tools] == ["render"]
    assert len(Transcript(path).messages()) == 1  # the engine reads bytes, and repairs this same file


def test_a_long_refusal_keeps_its_head_and_its_tail_and_says_where_it_was_cut(tmp_path: Path) -> None:
    """craft_run answers with the log of its steps: the error can be at the end."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append(turn(use("u1", "craft_run")))
    log = "passo 1 ok\n" + "x" * 5000 + "\nstep 9 (select.set): no such object"
    transcript.append(results(answer("u1", log, error=True)))
    (call,) = JsonlTranscripts(layout).read().calls
    assert call.refusal is not None and len(call.refusal) == 2000
    assert call.refusal.startswith("passo 1 ok") and call.refusal.endswith("no such object")
    assert "\n[…]\n" in call.refusal


PIXEL = base64.b64encode(b"\x89PNG\r\n\x1a\n un pixel").decode()


def image_block(media_type: str = "image/png", data: str = PIXEL) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def replayed(tmp_path: Path) -> DataLayout:
    """An instance as the engine writes it: the task, two turns, a reminder, the outcome."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append({"role": "user", "content": "TICKET T-0002: il segno"})
    transcript.append(
        turn(
            {"type": "thinking", "thinking": "Prima guardo il render", "signature": "firma"},
            {"type": "redacted_thinking", "data": "illeggibile"},
            {"type": "text", "text": "Guardo il file"},
            {"type": "tool_use", "id": "u1", "name": "view_image", "input": {"path": "segno.png"}},
            {"type": "tool_use", "id": "u2", "name": "deliver", "input": {}},
        ),
        request_id="req_1",
    )
    shown = {
        "type": "tool_result",
        "tool_use_id": "u1",
        "content": [{"type": "text", "text": "il render"}, image_block()],
    }
    transcript.append(results(shown, answer("u2", "consegna rifiutata", error=True)))
    transcript.append({"role": "user", "content": "Ricorda di consegnare"})
    transcript.append(turn(use("u3", "view_image")), request_id="req_2")
    transcript.append(
        results({"type": "tool_result", "tool_use_id": "u3", "content": [image_block("image/svg+xml")]})
    )
    transcript.finish(Outcome(state=OutcomeState.DELIVERED, note="fatto"))
    return layout


def test_a_transcript_reads_as_the_task_then_turn_after_turn(tmp_path: Path) -> None:
    record = JsonlTranscripts(replayed(tmp_path)).transcript("merlo4", "T-0002-a1")
    assert record is not None
    assert (record.task, record.outcome_state, record.outcome_note, record.unreadable) == (
        "TICKET T-0002: il segno",
        "delivered",
        "fatto",
        0,
    )
    first, second = record.turns
    assert (first.request_id, first.thinking, first.hidden_thinking, first.text) == (
        "req_1",
        ["Prima guardo il render"],
        1,
        ["Guardo il file"],
    )
    assert [(tool.name, tool.answered, tool.refused, tool.result) for tool in first.tools] == [
        ("view_image", True, False, "il render"),
        ("deliver", True, True, "consegna rifiutata"),
    ]
    assert json.loads(first.tools[0].input) == {"path": "segno.png"}
    assert [(image.index, image.media_type, image.servable) for image in first.tools[0].images] == [
        (0, "image/png", True)
    ]
    assert (first.notes, second.request_id) == (["Ricorda di consegnare"], "req_2")
    # An image of a type the dashboard does not serve is counted, but not offered.
    assert [(image.index, image.media_type, image.servable) for image in second.tools[0].images] == [
        (1, "image/svg+xml", False)
    ]
    assert record.images == 2


def test_an_image_comes_out_of_its_transcript_only_if_it_is_a_picture(tmp_path: Path) -> None:
    transcripts = JsonlTranscripts(replayed(tmp_path))
    picture = transcripts.image("merlo4", "T-0002-a1", 0)
    assert picture is not None and (picture.media_type, picture.data) == (
        "image/png",
        base64.b64decode(PIXEL),
    )
    assert transcripts.image("merlo4", "T-0002-a1", 1) is None  # SVG: it could hold scripts
    assert transcripts.image("merlo4", "T-0002-a1", 2) is None


def test_a_name_that_is_not_an_instance_never_becomes_a_path(tmp_path: Path) -> None:
    """Two defences, each with its own case: the name must be an instance's, and the file must be in the
    transcripts folder."""
    transcripts = JsonlTranscripts(replayed(tmp_path))
    line = '{"message": {"role": "user", "content": "x"}}\n'
    (tmp_path / "segreto.jsonl").write_text(line, encoding="utf-8")
    (tmp_path / "runs" / "merlo4" / "appunti.jsonl").write_text(
        line, encoding="utf-8"
    )  # inside, not an instance
    (tmp_path / "fuori").mkdir()
    (tmp_path / "fuori" / "T-0002-a1.jsonl").write_text(line, encoding="utf-8")  # an instance, but outside
    assert transcripts.transcript("merlo4", "appunti") is None
    assert transcripts.transcript("../fuori", "T-0002-a1") is None
    assert transcripts.image("../fuori", "T-0002-a1", 0) is None
    nested = tmp_path / "runs" / "acme" / "v2"  # inside the folder, but not a project name (COR-013)
    nested.mkdir(parents=True)
    (nested / "T-0002-a1.jsonl").write_text(line, encoding="utf-8")
    assert transcripts.transcript("acme/v2", "T-0002-a1") is None
    assert transcripts.image("acme/v2", "T-0002-a1", 0) is None
    for project, instance in [
        ("..", "segreto"),
        ("merlo4", "../../segreto"),
        ("merlo4", "T-0099-a1"),
        ("../merlo4", "T-0002-a1"),
    ]:
        assert transcripts.transcript(project, instance) is None, (project, instance)
        assert transcripts.image(project, instance, 0) is None


def test_missing_transcripts_are_not_an_error(tmp_path: Path) -> None:
    transcripts = JsonlTranscripts(DataLayout(tmp_path))
    assert (transcripts.read().calls, transcripts.read().unreadable, transcripts.stamp()) == ([], 0, [])


# The registry, read-only


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


def evidence(ticket_id: str, check: str, result: str, note: str) -> EvidenceRow:
    return EvidenceRow(
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


class FakeRegistry:
    def __init__(self, revision: str | None) -> None:
        self._revision = revision

    def stamp(self) -> list[SourceStamp]:
        return [SourceStamp(name="ledger.sqlite", size=1, modified_ns=1)]

    def revision(self) -> str | None:
        return self._revision

    def read(self) -> LedgerSnapshot:
        calls = [usage(), usage(seq=2, request_id="req_2", phase="director-plan", duration_ms=10)]
        return LedgerSnapshot(
            usage=calls,
            tickets=TICKETS,
            projects=[],
            gates=[],
            concepts=[],
            judgments=[],
            events=[],
            checks=[],
            runs=[],
        )


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


# The projection


def call(seq: int, project: str = "merlo3") -> Call:
    (projected,) = project_calls([usage(seq=seq, project=project, request_id=f"req_{seq}")], TICKETS, {})
    return projected


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


def event(seq: int, project: str, action: Lifecycle) -> EventRecord:
    return EventRecord(
        seq=seq,
        at=f"2026-11-02T10:0{seq}:00+00:00",
        project=project,
        ticket_id="T-0002",
        actor="x",
        action=action,
        reason="perché" if action is Lifecycle.BLOCK else None,
    )


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
