"""La vista Confronto: due progetti affiancati, cosa è cambiato nell'impronta, e i giudizi alla cieca."""

from __future__ import annotations

from agency.contracts.run import Fingerprint
from agency.insights import compare
from agency.insights.domain import (
    Call,
    CheckRecord,
    JudgmentRecord,
    Measures,
    PhaseSource,
    ProjectRecord,
    Provenance,
    RunRecord,
    ToolCallRecord,
)
from agency.insights.ports import ProjectData

PROVENANCE = Provenance(
    built_at="2026-11-03T12:00:00+00:00",
    sources=[],
    registry_revision="0005",
    calls=0,
    from_registry=0,
    from_traces=0,
    unmeasured=0,
    phases_recorded=0,
    phases_derived=0,
    unreadable_trace_lines=0,
    unreadable_transcript_lines=0,
)


def call(
    seq: int, project: str, minute: int, phase: str, cost: float, run: int | None, context: int = 100
) -> Call:
    return Call(
        seq=seq,
        at=f"2026-11-02T10:{minute:02d}:00+00:00",
        project=project,
        run=run,
        ticket_id="T-0001",
        ticket_type="",
        role="identity-designer",
        instance=f"T-0001-a{seq}",
        phase=phase,
        phase_source=PhaseSource.RECORDED,
        model="claude-opus-5-5",
        effort=None,
        input_tokens=context,
        output_tokens=10,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        cost_usd=cost,
        stop_reason="tool_use",
        request_id=f"req_{seq}",
        duration_ms=None,
        ttft_ms=None,
        reasoning_tokens=None,
        measures=Measures.MISSING,
    )


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


def run(seq: int, project: str, command: str, print_: Fingerprint | str) -> RunRecord:
    text = print_ if isinstance(print_, str) else print_.model_dump_json()
    digest = "illeggibile" if isinstance(print_, str) else print_.digest()
    return RunRecord(
        seq=seq,
        at=f"2026-11-02T09:{seq:02d}:00+00:00",
        project=project,
        command=command,
        digest=digest,
        fingerprint_json=text,
    )


def vote(
    seq: int, comparison: str, letter: str, project: str, level: str, *, best: bool, compared: int
) -> JudgmentRecord:
    return JudgmentRecord(
        seq=seq,
        at=f"2026-11-03T10:0{seq}:00+00:00",
        comparison=comparison,
        judge="Andrea",
        letter=letter,
        project=project,
        file="segno.svg",
        sha256="e" * 64,
        level=level,
        specific=best,
        best=best,
        why=f"perché {letter}",
        compared=compared,
    )


def data(calls: list[Call], runs: list[RunRecord], **extra: object) -> ProjectData:
    base: dict[str, object] = {
        "project": None,
        "calls": calls,
        "tickets": [],
        "gates": [],
        "concepts": [],
        "judgments": [],
        "events": [],
        "checks": [],
        "tool_calls": [],
        "runs": runs,
    }
    return ProjectData.model_validate(base | extra)


BEFORE = data(
    [
        call(1, "merlo3", 0, "explorer", 2.0, 1),
        call(2, "merlo3", 10, "finisher", 5.0, 2, context=9000),
    ],
    [run(1, "merlo3", "run", fingerprint()), run(2, "merlo3", "decide", fingerprint(explorers=3))],
    checks=[
        CheckRecord(
            seq=1,
            at="2026-11-02T10:05:00+00:00",
            project="merlo3",
            ticket_id="T-0001",
            file="segno.svg",
            check_name="svg_audit",
            result="FAIL",
            signer="tool",
            reason="nodi",
        )
    ],
    tool_calls=[
        ToolCallRecord(seq=1, project="merlo3", instance="T-0001-a1", turn=1, tool="deliver", refusal="no")
    ],
)
AFTER = data(
    [
        call(3, "merlo4", 0, "explorer", 1.0, 3),
        call(4, "merlo4", 4, "proposer", 1.5, 3),
        call(5, "merlo4", 6, "proposer", 0.5, None),
    ],
    [
        run(
            3,
            "merlo4",
            "run",
            fingerprint(explorers=3, effort="max", prompts={"prompts/roles/critic.md": "f" * 64}),
        )
    ],
)


def report(
    before: ProjectData = BEFORE, after: ProjectData = AFTER, judgments: list[JudgmentRecord] | None = None
):
    return compare.compare_report("merlo3", before, "merlo4", after, judgments or [], PROVENANCE)


def test_each_side_says_what_it_cost_how_long_it_took_and_where_it_went_wrong() -> None:
    before, after = report().before, report().after
    assert (before.project, before.cost_usd, before.calls, before.working_minutes, before.peak_context) == (
        "merlo3",
        7.0,
        2,
        10.0,
        9000,
    )
    assert (before.subjects, before.first_pass, before.tool_uses, before.tool_refusals) == (1, 0, 1, 1)
    assert (before.waiting_minutes, after.waiting_minutes) == (0.0, 0.0)
    assert (after.project, after.cost_usd, after.calls, after.subjects, after.tool_uses) == (
        "merlo4",
        3.0,
        3,
        0,
        0,
    )


def test_a_project_without_its_record_says_so_instead_of_looking_like_the_default() -> None:
    """merlo3 qui non ha la riga del progetto: modello ed effort non sono registrati, non predefiniti."""
    chosen = ProjectRecord(name="merlo4", budget_usd=30.0, model="", effort="max")
    sides = report(after=data(AFTER.calls, AFTER.runs, project=chosen))
    assert (sides.before.model, sides.before.effort, sides.before.budget_usd) == (None, None, None)
    assert (sides.after.model, sides.after.effort, sides.after.budget_usd) == ("", "max", 30.0)


def test_the_fingerprints_compared_are_the_last_one_before_and_the_first_one_after() -> None:
    """merlo3 finisce con explorers=3 (decide #2): verso merlo4 cambiano effort e un prompt, non explorers."""
    later = run(4, "merlo4", "resume", fingerprint(explorers=9))
    diff = report(after=data(AFTER.calls, [*AFTER.runs, later])).fingerprint
    assert (diff.state, diff.before_run, diff.after_run) == (compare.Compared.BOTH, 2, 3)
    assert [(item.part, item.item, item.before, item.after) for item in diff.changes] == [
        ("effort", "", "high", "max"),
        ("prompts", "prompts/roles/critic.md", "a" * 64, "f" * 64),
    ]


def test_every_execution_says_what_it_spent_and_how_far_it_is_from_the_one_before() -> None:
    """La chiamata senza esecuzione è di prima delle impronte: non si conta in nessuna."""
    before, after = report().before.executions, report().after.executions
    assert [
        (item.seq, item.command, item.calls, item.cost_usd, item.changes_from_previous) for item in before
    ] == [
        (1, "run", 1, 2.0, None),
        (2, "decide", 1, 5.0, 1),
    ]
    assert [(item.seq, item.calls, item.cost_usd, item.readable) for item in after] == [(3, 2, 2.5, True)]
    assert report().after.unrecorded_calls == 1


def test_without_a_fingerprint_on_one_side_nothing_is_compared_and_the_report_says_which() -> None:
    no_runs = data(BEFORE.calls, [])
    assert report(before=no_runs).fingerprint.state is compare.Compared.NOT_BEFORE
    assert report(after=data(AFTER.calls, [])).fingerprint.state is compare.Compared.NOT_AFTER
    assert report(before=no_runs, after=data(AFTER.calls, [])).fingerprint.state is compare.Compared.NEITHER
    assert report(before=no_runs).fingerprint.changes == []


def test_a_fingerprint_this_version_cannot_read_is_said_not_guessed() -> None:
    """Un'impronta di una forma che il contratto non conosce più resta nell'elenco, ma non si confronta."""
    runs = [
        run(1, "merlo3", "run", fingerprint()),
        run(2, "merlo3", "decide", '{"model": 1}'),
        run(3, "merlo3", "resume", fingerprint(explorers=3)),
    ]
    side = report(before=data(BEFORE.calls, runs))
    # La #3 si confronta con l'ultima leggibile, la #1.
    assert [(item.seq, item.readable, item.changes_from_previous) for item in side.before.executions] == [
        (1, True, None),
        (2, False, None),
        (3, True, 1),
    ]
    assert (side.fingerprint.state, side.fingerprint.before_run) == (compare.Compared.BOTH, 3)
    only_unreadable_last = data(BEFORE.calls, runs[:2])
    assert report(before=only_unreadable_last).fingerprint.before_run == 1


def test_phases_stand_side_by_side_in_the_order_of_the_newer_work() -> None:
    assert [(item.phase, item.before_usd, item.after_usd) for item in report().phases] == [
        ("explorer", 2.0, 1.0),
        ("proposer", None, 2.0),
        ("finisher", 5.0, None),
    ]


def test_a_blind_judgment_counts_when_both_projects_are_in_it_and_shows_every_vote() -> None:
    """Il confronto x ha anche un file esterno: si vede, con la sua lettera. Il confronto y ha solo merlo3."""
    judgments = [
        vote(1, "x", "C", "", "ordinario", best=False, compared=3),
        vote(2, "x", "A", "merlo3", "ordinario", best=False, compared=3),
        vote(3, "x", "B", "merlo4", "buono", best=True, compared=3),
        vote(4, "y", "A", "merlo3", "buono", best=False, compared=1),
    ]
    (judged,) = report(judgments=judgments).judgments
    assert (judged.comparison, judged.judge, judged.at) == ("x", "Andrea", "2026-11-03T10:01:00+00:00")
    assert [(item.letter, item.project, item.level, item.best) for item in judged.votes] == [
        ("A", "merlo3", "ordinario", False),
        ("B", "merlo4", "buono", True),
        ("C", "", "ordinario", False),
    ]
