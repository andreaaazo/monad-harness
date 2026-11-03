"""Il rapporto di un progetto: un modello solo per il testo, il JSON e il cruscotto (M1.6, punto 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agency import cli
from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.insights import views
from agency.insights.domain import (
    Call,
    ConceptRecord,
    GateRecord,
    JudgmentRecord,
    Measures,
    PhaseSource,
    ProjectRecord,
    Provenance,
    TicketRecord,
)
from agency.insights.ports import ProjectData
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow, GateRow, UsageRow

PROVENANCE = Provenance(
    built_at="2026-11-02T12:00:00+00:00",
    sources=[],
    registry_revision="0005",
    calls=0,
    from_registry=0,
    from_traces=0,
    unmeasured=0,
    phases_recorded=0,
    phases_derived=0,
    unreadable_trace_lines=0,
)


def call(seq: int, at: str, **extra: object) -> Call:
    base: dict[str, object] = {
        "seq": seq,
        "at": at,
        "project": "merlo3",
        "run": None,
        "ticket_id": "T-0001",
        "ticket_type": "consegna",
        "role": "design-director",
        "instance": "T-0001-a1",
        "phase": "design-director",
        "phase_source": PhaseSource.DERIVED,
        "model": "claude-opus-5-5",
        "effort": None,
        "input_tokens": 100,
        "output_tokens": 10,
        "cache_read_tokens": 300,
        "cache_write_5m_tokens": 100,
        "cache_write_1h_tokens": 0,
        "cost_usd": 1.0,
        "stop_reason": "tool_use",
        "request_id": f"req_{seq}",
        "duration_ms": None,
        "ttft_ms": None,
        "reasoning_tokens": None,
        "measures": Measures.MISSING,
    }
    return Call.model_validate(base | extra)


def ticket(id_: str, **extra: object) -> TicketRecord:
    base: dict[str, object] = {
        "id": id_,
        "project": "merlo3",
        "type": "consegna",
        "assignee": "design-director",
        "prompt": "",
        "title": "Consegna merlo3",
        "status": "open",
        "verdict": None,
        "created_at": "2026-11-02T10:00:00+00:00",
    }
    return TicketRecord.model_validate(base | extra)


def data(calls: list[Call], **extra: object) -> ProjectData:
    base: dict[str, object] = {
        "project": ProjectRecord(name="merlo3", budget_usd=50.0, model="", effort=""),
        "calls": calls,
        "tickets": [
            ticket("T-0001"),
            ticket("T-0002", type="schizzo", assignee="direction-a", title="Schizzi a"),
        ],
        "gates": [],
        "concepts": [],
        "judgments": [],
    }
    return ProjectData.model_validate(base | extra)


T0, T1, T2, T3 = (f"2026-11-02T10:{minute:02d}:00+00:00" for minute in (0, 10, 30, 45))


# I numeri


def test_cost_calls_cache_and_context_of_a_project() -> None:
    report = views.project_report("merlo3", data([call(1, T0), call(2, T1, cost_usd=0.5)]), PROVENANCE)
    assert (report.cost_usd, report.calls, report.budget_usd) == (1.5, 2, 50.0)
    assert report.cache_hit == pytest.approx(300 / 500)
    assert report.mean_context == 500


def test_cost_until_the_approved_concept_gate_is_what_came_before_it() -> None:
    gates = [
        GateRecord(seq=1, at=T1, project="merlo3", gate="concept", approved=False, choice=""),
        GateRecord(seq=2, at=T2, project="merlo3", gate="concept", approved=True, choice="X"),
    ]
    calls = [
        call(1, T0, cost_usd=2.0),
        call(2, T1, cost_usd=3.0),
        call(3, T2, cost_usd=4.0),
        call(4, T3, cost_usd=8.0),
    ]
    milestone = views.project_report("merlo3", data(calls, gates=gates), PROVENANCE).to_presentation
    assert milestone == views.Milestone(cost_usd=9.0, calls=3, minutes=30.0)


def test_no_approved_concept_gate_means_no_milestone() -> None:
    gates = [GateRecord(seq=1, at=T1, project="merlo3", gate="concept", approved=False, choice="")]
    assert (
        views.project_report("merlo3", data([call(1, T0)], gates=gates), PROVENANCE).to_presentation is None
    )


def test_peak_counts_instances_working_together() -> None:
    """a lavora da T0 a T2, b da T1 a T3: insieme solo per la loro durata. c arriva quando a ha finito."""
    plan = [(T0, "a"), (T2, "a"), (T1, "b"), (T3, "b"), (T3, "c")]
    calls = [call(seq, at, instance=name) for seq, (at, name) in enumerate(plan, start=1)]
    assert views.project_report("merlo3", data(calls), PROVENANCE).parallel == 2
    one_after_another = [call(1, T0, instance="a"), call(2, T1, instance="a"), call(3, T2, instance="b")]
    assert views.project_report("merlo3", data(one_after_another), PROVENANCE).parallel == 1


def test_roles_are_ordered_by_cost_and_types_by_first_appearance() -> None:
    calls = [
        call(1, T0, role="direction-a", ticket_id="T-0002", ticket_type="schizzo", cost_usd=1.0),
        call(2, T1, cost_usd=5.0),
        call(3, T2, role="direction-a", ticket_id="T-0002", ticket_type="schizzo", cost_usd=1.0),
    ]
    report = views.project_report("merlo3", data(calls), PROVENANCE)
    assert [(role.role, role.calls, role.cost_usd) for role in report.roles] == [
        ("design-director", 1, 5.0),
        ("direction-a", 2, 2.0),
    ]
    assert [(item.ticket_type, item.cost_usd) for item in report.ticket_types] == [
        ("schizzo", 2.0),
        ("consegna", 5.0),
    ]
    assert [(item.id, item.cost_usd) for item in report.tickets] == [("T-0001", 5.0), ("T-0002", 2.0)]


def test_phases_say_how_the_model_worked_and_how_much_was_measured() -> None:
    calls = [
        call(
            1,
            T0,
            phase="explorer",
            duration_ms=4000,
            ttft_ms=900,
            reasoning_tokens=50,
            measures=Measures.TRACES,
        ),
        call(
            2,
            T1,
            phase="explorer",
            duration_ms=8000,
            ttft_ms=1500,
            reasoning_tokens=70,
            measures=Measures.REGISTRY,
        ),
        call(
            3,
            T2,
            phase="explorer",
            duration_ms=6000,
            ttft_ms=1100,
            reasoning_tokens=None,
            measures=Measures.REGISTRY,
        ),
        call(4, T3, phase="critic", cost_usd=3.0),
    ]
    phases = {phase.phase: phase for phase in views.project_report("merlo3", data(calls), PROVENANCE).phases}
    explorer = phases["explorer"]
    assert (explorer.calls, explorer.measured, explorer.mean_duration_ms) == (3, 3, 6000.0)
    assert (explorer.median_ttft_ms, explorer.reasoning_tokens) == (1100, 120)
    critic = phases["critic"]
    assert (critic.calls, critic.measured, critic.mean_duration_ms, critic.median_ttft_ms) == (
        1,
        0,
        None,
        None,
    )
    assert list(phases) == ["critic", "explorer"]  # per costo: 3,00 $ contro 3,00 $, poi in ordine di nome


def test_ideas_judgments_and_tickets_are_part_of_the_report() -> None:
    concepts = [
        ConceptRecord(
            seq=1,
            project="merlo3",
            round=1,
            letter="a",
            anon="X",
            lever="il nome",
            status="proposta",
            concept="Una ruota",
        )
    ]
    judgments = [
        JudgmentRecord(
            seq=1,
            at=T3,
            comparison="c1",
            judge="andrea",
            letter="A",
            project="merlo3",
            file="exports/segno.svg",
            sha256="a" * 64,
            level="eccellente",
            specific=True,
            best=True,
            why="Unico",
            compared=2,
        )
    ]
    report = views.project_report(
        "merlo3", data([call(1, T0)], concepts=concepts, judgments=judgments), PROVENANCE
    )
    assert [(idea.anon, idea.concept) for idea in report.ideas] == [("X", "Una ruota")]
    assert [(judged.letter, judged.best, judged.compared) for judged in report.judgments] == [("A", True, 2)]


def test_the_run_has_its_start_its_end_and_a_timeline_of_instances() -> None:
    """In ordine di inizio, non di nome: T-0001-a1-present precede T-0002-a1 solo in ordine alfabetico."""
    director = {"instance": "T-0001-a1-plan", "phase": "director-plan", "cost_usd": 0.5}
    explorer = {"instance": "T-0002-a1", "ticket_id": "T-0002", "role": "direction-a", "phase": "explorer"}
    present = {"instance": "T-0001-a1-present", "phase": "director-present", "cost_usd": 0.25}
    calls = [
        call(1, T0, **director, duration_ms=3000),
        call(2, T1, **explorer, cost_usd=1.0),
        call(3, T1, **director, duration_ms=1000),
        call(4, T2, **explorer, cost_usd=2.0, duration_ms=5000, measures=Measures.REGISTRY),
        call(5, T3, **present),
    ]
    report = views.project_report("merlo3", data(calls), PROVENANCE)
    assert (report.started_at, report.ended_at) == (T0, T3)
    timeline = [
        (item.instance, item.started_at, item.ended_at, item.calls, item.cost_usd)
        for item in report.instances
    ]
    assert timeline == [
        ("T-0001-a1-plan", T0, T1, 2, 1.0),
        ("T-0002-a1", T1, T2, 2, 3.0),
        ("T-0001-a1-present", T3, T3, 1, 0.25),
    ]
    second = report.instances[1]
    assert (second.ticket_id, second.role, second.phase, second.model_ms) == (
        "T-0002",
        "direction-a",
        "explorer",
        5000,
    )


def test_an_instance_without_measures_says_so() -> None:
    (instance,) = views.project_report("merlo3", data([call(1, T0)]), PROVENANCE).instances
    assert instance.model_ms is None


def gate(seq: int, at: str, *, approved: bool = True) -> GateRecord:
    return GateRecord(seq=seq, at=at, project="merlo3", gate="concept", approved=approved, choice="X")


def test_waiting_for_the_client_is_not_work() -> None:
    """Il run si ferma dopo la presentazione e riparte alla decisione: l'attesa si conta a parte."""
    decided = "2026-11-02T10:40:00+00:00"
    calls = [call(1, T0), call(2, T1), call(3, T3)]
    report = views.project_report("merlo3", data(calls, gates=[gate(1, decided)]), PROVENANCE)
    assert [(wait.gate, wait.started_at, wait.ended_at, wait.minutes) for wait in report.waits] == [
        ("concept", T1, decided, 30.0)
    ]
    assert (report.elapsed_minutes, report.working_minutes) == (45.0, 15.0)


def test_waits_never_overlap_and_a_decision_without_a_restart_is_not_a_wait() -> None:
    """Respinto alle 10:20, approvato alle 10:25 senza lavoro in mezzo: la seconda attesa parte dalla prima
    decisione. Una decisione dopo l'ultima chiamata non ferma niente: il run non è ripartito."""
    calls = [call(1, T0), call(2, T1), call(3, T2)]
    gates = [
        gate(1, "2026-11-02T10:20:00+00:00", approved=False),
        gate(2, "2026-11-02T10:25:00+00:00"),
        gate(3, "2026-11-02T10:50:00+00:00"),
    ]
    report = views.project_report("merlo3", data(calls, gates=gates), PROVENANCE)
    assert [(wait.started_at, wait.minutes) for wait in report.waits] == [
        (T1, 10.0),
        ("2026-11-02T10:20:00+00:00", 5.0),
    ]
    assert (report.elapsed_minutes, report.working_minutes) == (30.0, 15.0)


def test_a_run_without_decisions_is_all_work() -> None:
    report = views.project_report("merlo3", data([call(1, T0), call(2, T2)]), PROVENANCE)
    assert (report.waits, report.elapsed_minutes, report.working_minutes) == ([], 30.0, 30.0)


def test_a_project_without_calls_has_a_report_of_zeros() -> None:
    empty = ProjectData(project=None, calls=[], tickets=[], gates=[], concepts=[], judgments=[])
    report = views.project_report("fantasma", empty, PROVENANCE)
    assert (report.cost_usd, report.calls, report.cache_hit, report.mean_context, report.parallel) == (
        0.0,
        0,
        0.0,
        0.0,
        0,
    )
    assert report.budget_usd is None and report.to_presentation is None
    assert (report.started_at, report.ended_at, report.instances) == (None, None, [])
    assert (report.elapsed_minutes, report.working_minutes, report.waits) == (0.0, 0.0, [])


# Il comando, dal registro al testo e al JSON


def usage(seq: int, at: str, **extra: object) -> UsageRow:
    base: dict[str, object] = {
        "at": at,
        "project": "officina",
        "ticket_id": "T-0001",
        "role": "design-director",
        "instance": "T-0001-a1-plan",
        "model": "claude-opus-5-5",
        "input_tokens": 100,
        "output_tokens": 20,
        "cost_usd": 1.25,
        "stop_reason": "tool_use",
        "request_id": f"req_{seq}",
    }
    return UsageRow.model_validate(base | extra)


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    from agency.contracts.ticket import TicketSpec, TicketType

    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ledger.set_project("officina", 30)
    spec = TicketSpec(
        title="Consegna officina",
        request="r",
        type=TicketType.DELIVERY,
        sender="router",
        assignee="design-director",
        outputs=["segno.svg"],
        checks={"*.svg": ["svg_audit"]},
    )
    ledger.open(spec, "officina")
    ledger.record_usage(usage(1, T0))
    ledger.record_usage(usage(2, T1, phase="director-plan", effort="high", duration_ms=4000, ttft_ms=800))
    ledger.add_gate(
        GateRow(at=T1, project="officina", gate="concept", approved=True, choice="X", files_json="{}")
    )
    ledger.record_usage(usage(3, T2, instance="T-0001-a2"))
    ledger.add_concept(
        ConceptRow(project="officina", round=1, letter="a", lever="il nome", idea_ticket="T-0001", anon="X")
    )
    judgment = Judgment(
        judge="andrea", ratings=[Rating(letter="A", level=Level.GOOD, specific=True, why="Regge")]
    )
    ledger.record_judgment(
        "c1", judgment, {"A": Judged(project="officina", file="segno.svg", sha256="b" * 64)}
    )
    return ledger


def test_report_json_is_the_model_and_reproduces_the_numbers(
    studio: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["report", "officina", "--json"]) == 0
    report = views.ProjectReport.model_validate_json(capsys.readouterr().out)
    assert (report.cost_usd, report.calls, report.budget_usd) == (3.75, 3, 30.0)
    assert report.to_presentation == views.Milestone(cost_usd=2.5, calls=2, minutes=10.0)
    assert [(p.phase, p.calls, p.measured) for p in report.phases] == [
        ("director-plan", 2, 1),
        ("design-director", 1, 0),
    ]
    assert report.provenance.calls == 3
    assert json.loads(report.model_dump_json())["phases"][0]["median_ttft_ms"] == 800


def test_report_text_comes_from_the_same_model(studio: Ledger, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["report", "officina"]) == 0
    text = capsys.readouterr().out
    assert "Progetto officina: 3.75 $ su 30.00 $ in 3 chiamate" in text
    assert "Fino alla presentazione: 2.50 $ in 10.0 minuti" in text
    assert "Costo per tipo di lavoro: consegna 3.75 $" in text
    assert "director-plan" in text and "4.0 s" in text and "0.8 s" in text
    assert "r1 X [idea] il nome" in text
    assert "segno.svg [A] buono, specifico" in text
    assert "T-0001 open → design-director: Consegna officina (3.75 $)" in text


def test_report_never_writes_the_registry(studio: Ledger, tmp_path: Path) -> None:
    import hashlib

    studio.engine.dispose()
    before = hashlib.sha256((tmp_path / "ledger.sqlite").read_bytes()).hexdigest()
    assert cli.main(["report", "officina", "--json"]) == 0
    assert hashlib.sha256((tmp_path / "ledger.sqlite").read_bytes()).hexdigest() == before
