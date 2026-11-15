"""A whole project with real Craft and recorded answers: budget, model and effort, fingerprints and kept
files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from agency.agents.toolbox import TOOLS, Toolbox, tools_for
from agency.artifacts import FileStore
from agency.contracts.concept import ConceptCard
from agency.contracts.run import Fingerprint, changes
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.gateway import BudgetExceeded
from agency.insights.adapters.ledger import ReadOnlyLedger
from agency.insights.domain import derive_phase
from agency.ledger import Ledger
from agency.process.session import open_session
from agency.studio.exploration.tools import EXPLORE, PLAN
from agency.studio.presentation.tools import PRESENT
from agency.studio.proposal.tools import PROPOSAL
from agency.studio.selection.tools import SELECT
from support.rules import RULES
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    MASTER,
    OUTPUTS,
    SVG,
    WHY,
    Router,
    brief,
    card,
    context,
    exploration,
    full_script,
    plan_turn,
    to_the_gate,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_each_phase_has_only_its_tools() -> None:
    base = TicketSpec(
        title="Esplorazione",
        request="r",
        type=TicketType.SKETCH,
        sender="d",
        assignee="c",
        outputs=["a"],
        checks={"a": ["master_open"]},
        media=[Medium.VECTOR],
    )
    assert {tool.name for tool in tools_for(RULES, "direction-a", base)} == set(EXPLORE)
    proposal = base.model_copy(update={"type": TicketType.PROPOSAL})
    assert {tool.name for tool in tools_for(RULES, "identity-designer", proposal)} == set(PROPOSAL)
    assert {t.name for t in tools_for(RULES, "design-director", base, "plan")} == set(PLAN)
    assert {t.name for t in tools_for(RULES, "design-director", base, "select")} == set(SELECT)
    assert {t.name for t in tools_for(RULES, "design-director", base, "present")} == set(PRESENT)
    assert all(name in TOOLS for name in (*EXPLORE, *PLAN, *SELECT, *PRESENT, *PROPOSAL))


def test_concept_card_schema_is_complete() -> None:
    assert set(ConceptCard.model_json_schema()["required"]) == set(card("x"))


def test_no_limit_on_the_number_of_tools(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x")
    box = Toolbox(context(tmp_path), [TOOLS["read_file"]])
    results = [box.call(f"c{n}", "read_file", {"path": "a.md"}) for n in range(200)]
    assert not any(result.get("is_error") for result in results)


def test_number_of_images_never_blocks_the_work(tmp_path: Path) -> None:
    box = Toolbox(context(tmp_path), [TOOLS["view_image"]])
    for number in range(60):
        Image.new("RGB", (20, 20), (number, 0, 0)).save(tmp_path / f"i{number}.png")
        assert not box.call(f"c{number}", "view_image", {"path": f"i{number}.png"}).get("is_error")


def test_agents_never_hear_about_budget(tmp_path: Path) -> None:
    transport = Router(to_the_gate())
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=1000)
    calls = [call for calls in transport.requests.values() for call in calls]
    assert calls
    for call in calls:  # the tool schemas hold `$ref`: what counts is what the agent reads
        readable = json.dumps([call["system"], call["messages"]], ensure_ascii=False).lower()
        assert "budget" not in readable and "quota" not in readable
        assert " $" not in readable
        descriptions = [tool["description"].lower() for tool in call["tools"]]
        assert not any("budget" in text or "quota" in text for text in descriptions)


def test_client_chooses_model_and_effort_for_the_whole_project(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start(
        "officina", brief(tmp_path), OUTPUTS, CHECKS, budget=9, model="claude-sonnet-5-5", effort="medium"
    )
    sent = transport.requests["T-0003"][0]
    assert sent["model"] == "claude-sonnet-5-5" and sent["output_config"] == {"effort": "medium"}
    assert transport.requests["T-0001:plan"][0]["model"] == "claude-sonnet-5-5"
    assert session.ledger.project("officina").budget_usd == 9  # type: ignore[union-attr]


def test_budget_end_pauses_the_project_and_an_increase_resumes_it(tmp_path: Path) -> None:
    config = settings(tmp_path)
    session = open_session(config, Router(to_the_gate()))
    with pytest.raises(BudgetExceeded):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=0.09)
    session.ledger.set_budget("officina", 50)
    again = open_session(config, session_transport := Router(to_the_gate()))
    again.resume("officina")
    assert again.pending("officina")[0].gate == "concept"
    assert "T-0001:plan" not in session_transport.requests  # the plan already made is not paid for again


def fingerprints(ledger: Ledger, project: str) -> list[Fingerprint]:
    return [Fingerprint.model_validate_json(row.fingerprint_json) for row in ledger.runs(project)]


def test_every_execution_of_a_project_records_its_fingerprint(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(full_script()))
    session.start(
        "officina",
        brief(tmp_path),
        OUTPUTS,
        CHECKS,
        budget=BUDGET,
        model="claude-sonnet-5-5",
        effort="medium",
    )
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Approvato")
    runs = session.ledger.runs("officina")
    assert [row.command for row in runs] == ["run", "decide", "decide"]
    assert len({row.digest for row in runs}) == 1
    taken = fingerprints(session.ledger, "officina")[0]
    assert (taken.model, taken.effort) == ("claude-sonnet-5-5", "medium")


def test_every_call_knows_its_execution_and_phase(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    first, second = (row.seq for row in session.ledger.runs("officina"))
    usage = session.ledger.usage("officina")
    phases = {run: {row.phase for row in usage if row.run == run} for run in (first, second)}
    assert phases[first] == {
        "director-plan",
        "explorer",
        "critic-board",
        "director-select",
        "proposer",
        "director-present",
    }
    assert phases[second] == {"finisher", "design-director", "qa-inspector", "critic"}
    assert {row.run for row in usage} == {first, second}
    assert all(row.effort in {"high", "medium"} and row.duration_ms is not None for row in usage)


def test_everything_delivered_or_shown_to_the_client_is_kept(tmp_path: Path) -> None:
    config = settings(tmp_path)
    session = open_session(config, Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    (pdf,) = session.pending("officina")[0].files
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Approvato")

    store, ledger = FileStore(config.layout.artifacts), session.ledger
    rows = ledger.artifacts("officina")
    kept = {(row.ticket_id, row.path, row.sha256) for row in rows if row.origin == "consegna"}
    for ticket in ledger.tickets("officina"):
        for path, digest in json.loads(ticket.delivered_json).items():
            assert (ticket.id, path, digest) in kept
            assert store.intact(digest)
    (shown,) = [row for row in rows if row.origin == "presentazione"]
    assert (shown.path, shown.ticket_id, shown.media_type) == (pdf, "T-0001", "application/pdf")
    assert json.loads(ledger.gates("officina")[0].files_json) == {pdf: shown.sha256}
    assert {row.run for row in rows} <= {run.seq for run in ledger.runs("officina")}
    assert all(row.run is not None for row in rows)


def test_a_blocked_plan_ends_the_project_and_says_why(tmp_path: Path) -> None:
    script = {"T-0001:plan": [turn(use("block", reason="manca il nome del cliente"))]}
    session = open_session(settings(tmp_path), Router(script))
    outcome = session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert outcome == "bloccato: manca il nome del cliente"
    assert [row.id for row in session.ledger.tickets("officina")] == ["T-0001"]
    assert session.pending("officina") == []


def test_insights_derives_the_phase_the_engine_recorded_for_every_call(tmp_path: Path) -> None:
    """The rule that derives the phase of old calls is the one the engine uses for new ones."""
    config = settings(tmp_path)
    session = open_session(config, Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    snapshot = ReadOnlyLedger(config.layout.ledger).read()
    tickets, calls = snapshot.tickets, snapshot.usage
    assert len({call.phase for call in calls}) == 10
    for call in calls:
        assert call.phase is not None
        assert derive_phase(call, tickets) == call.phase


def test_resume_with_other_settings_shows_what_changed(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(to_the_gate()))
    with pytest.raises(BudgetExceeded):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=0.09)
    session.ledger.set_budget("officina", 50)
    again = open_session(settings(tmp_path, explorer_effort="medium"), Router(to_the_gate()))
    again.resume("officina")
    first, second = fingerprints(again.ledger, "officina")
    assert [row.command for row in again.ledger.runs("officina")] == ["run", "resume"]
    assert [(c.part, c.before, c.after) for c in changes(first, second)] == [
        ("explorer_effort", "high", "medium")
    ]


def test_judge_refuses_a_file_against_itself(tmp_path: Path) -> None:
    """The same file under another spelling is still itself. The file was viewed, so nothing else refuses."""
    ctx = context(tmp_path)
    Image.new("RGB", (60, 60), (20, 20, 20)).save(tmp_path / "segno.png")
    box = Toolbox(ctx, [TOOLS["view_image"], TOOLS["judge"]])
    box.call("a", "view_image", {"path": "segno.png"})

    arguments = {"file": "segno.png", "compare": ["./segno.png"], "why": WHY, "result": "PASS"}
    result = box.call("b", "judge", arguments)

    assert result["is_error"]
    assert result["content"] == "un file non si confronta con se stesso"


def test_export_master_refuses_unknown_options(tmp_path: Path) -> None:
    ctx = context(tmp_path, "identity-designer")
    box = Toolbox(ctx, [TOOLS["export_master"]])
    options = ["--scale", "2", "--plugin", "x.js"]

    result = box.call("a", "export_master", {"master": MASTER, "output": SVG, "options": options})

    assert result["is_error"]
    assert result["content"] == "opzioni non ammesse: ['--plugin']"
