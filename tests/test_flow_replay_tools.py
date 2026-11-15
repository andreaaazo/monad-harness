"""A tool already run is replayed on resume, not run again: the closing and the director's tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from agency.agents.toolbox import TOOLS, Toolbox
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.contracts.ledger import ConceptEntry, EvidenceEntry
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.files import sha256_under
from agency.workshop.sandbox import (
    Sandbox,
)
from support.flow import (
    DIRECTOR,
    SVG_PATH,
    closing_box,
    crash_after_the_transition,
    intact,
    needs_craft,
    production_spec,
    runner,
    use,
)
from support.rules import RULES
from support.scripted import turn
from support.settings import settings


class Killed(Exception):
    """The process dies here: nothing after this point reaches the disk."""


@needs_craft
def test_an_effect_tool_records_its_result_for_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Killed after its tools ran but before their results reached the transcript, an instance resumes without
    repeating any effect and closes as it did (TST-007, ADR-0002)."""
    config = settings(tmp_path)
    svg = "exports/segno.svg"
    spec = TicketSpec(
        title="Segno",
        request="Disegna il segno",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=[svg],
        checks={"*.svg": ["svg_audit"]},
        media=[Medium.NONE],
        medium_why="verifica del solo file, senza master",
    )
    batch = turn(
        use("run_check", "t1", check="svg_audit", file=svg),
        use("deliver", "t2", note="segno pronto", verdict=None),
    )
    run, transport, ledger = runner(config, [batch])
    ticket = ledger.open(spec, "p")
    work = config.project_dir(ProjectName("p")) / "work"
    (work / "exports").mkdir(parents=True)
    drawing = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="{SVG_PATH}"/></svg>'
    (work / svg).write_text(drawing)
    append = Transcript.append

    def die_before_the_results(self: Transcript, message: dict, request_id: str | None = None) -> None:
        if message["role"] == "user" and isinstance(message["content"], list):
            raise Killed
        append(self, message, request_id)

    monkeypatch.setattr(Transcript, "append", die_before_the_results)
    with pytest.raises(Killed):
        run.run(ticket)
    assert ledger.status(ticket)[0] is Status.DELIVERED  # the effects happened before the kill
    monkeypatch.setattr(Transcript, "append", append)
    outcome = run.run(ticket)
    assert outcome.state == "delivered"
    assert [row.check_name for row in ledger.evidence("p")] == ["svg_audit"]  # the check did not run twice
    instance = f"{ticket}-a1"
    assert ledger.operation(f"{instance}:t1") is not None
    assert ledger.operation(f"{instance}:t2") is not None
    assert len(transport.requests) == 1  # resume replayed the stored results without calling the model


def test_a_replayed_deliver_closes_as_delivered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = TicketSpec(
        title="Nota",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="copywriter",
        outputs=["nota.md"],
        checks={"*.md": ["req:letta"]},
        media=[Medium.NONE],
        medium_why="solo un testo di prova",
    )
    box, context, ticket = closing_box(tmp_path, spec, "copywriter", "record_requirement", "deliver")
    (tmp_path / "work" / "nota.md").write_text("v1")
    box.call(
        "a", "record_requirement", {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    )
    arguments = {"note": "fatto", "verdict": None}
    crash_after_the_transition(box, context, monkeypatch, "deliver", arguments)
    assert context.ledger.status(ticket)[0] is Status.DELIVERED

    result = box.call("t1", "deliver", arguments)

    assert not result.get("is_error"), result["content"]
    assert json.loads(result["content"]) == {"ok": True, "status": "delivered"}
    assert context.finished == Outcome(state=OutcomeState.DELIVERED, note="fatto")
    assert context.ledger.status(ticket)[0] is Status.DELIVERED
    assert [event.action for event in context.ledger.history(ticket)].count("deliver") == 1


def test_a_replayed_block_closes_as_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    box, context, ticket = closing_box(tmp_path, production_spec(), "identity-designer", "block")
    arguments = {"reason": "manca il brief"}
    crash_after_the_transition(box, context, monkeypatch, "block", arguments)
    assert context.ledger.status(ticket)[0] is Status.BLOCKED

    result = box.call("t1", "block", arguments)

    assert not result.get("is_error"), result["content"]
    assert json.loads(result["content"]) == {"ok": True, "status": "blocked"}
    assert context.finished == Outcome(state=OutcomeState.BLOCKED, note="manca il brief")
    assert [event.action for event in context.ledger.history(ticket)].count("block") == 1


def test_a_close_by_another_actor_is_not_taken_for_a_replay(tmp_path: Path) -> None:
    """Only the actor whose transition committed can replay it: anyone else still meets the ledger's rule."""
    box, context, ticket = closing_box(tmp_path, production_spec(), "identity-designer", "block")
    assert not box.call("t1", "block", {"reason": "manca il brief"}).get("is_error")
    other = ToolContext(
        "design-director",
        "p",
        ticket,
        "j",
        context.ledger,
        Sandbox(tmp_path / "work"),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    result = Toolbox(other, [TOOLS["block"]]).call("t2", "block", {"reason": "anche io"})
    assert result.get("is_error")
    assert "non è ammesso" in result["content"]
    assert [event.action for event in context.ledger.history(ticket)].count("block") == 1


def test_a_replayed_submit_concept_closes_as_delivered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = TicketSpec(
        title="Esplorazione A",
        request="r",
        type=TicketType.SKETCH,
        sender="design-director",
        assignee="direction-a",
        outputs=["scheda.json", "schizzo-a.png"],
        checks={"*.png": ["req:letta"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.NONE],
        medium_why="solo uno schizzo di prova",
    )
    concept = ConceptEntry(project="p", round=1, letter="a", lever="l", idea_ticket="")
    box, context, ticket = closing_box(
        tmp_path, spec, "direction-a", "record_requirement", "submit_concept", concept=concept
    )
    Image.new("RGB", (64, 64), (255, 255, 255)).save(tmp_path / "work" / "schizzo-a.png")
    box.call(
        "a",
        "record_requirement",
        {"file": "schizzo-a.png", "check": "req:letta", "result": "PASS", "note": "ok"},
    )
    card = {
        "concept": "un'idea",
        "client_fact": "un fatto",
        "why_not_obvious": "perché",
        "drawing": "un segno",
        "substitution": "non regge altrove",
    }
    crash_after_the_transition(box, context, monkeypatch, "submit_concept", card)
    assert context.ledger.status(ticket)[0] is Status.DELIVERED

    result = box.call("t1", "submit_concept", card)

    assert not result.get("is_error"), result["content"]
    assert json.loads(result["content"]) == {"ok": True}
    assert context.finished == Outcome(state=OutcomeState.DELIVERED, note="un'idea")
    assert [event.action for event in context.ledger.history(ticket)].count("deliver") == 1


def test_an_interrupted_plan_never_loses_a_direction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = settings(tmp_path)
    box, context, root = closing_box(tmp_path, DIRECTOR, "design-director", "plan_exploration")
    context.settings = config
    (tmp_path / "work" / "brief.md").write_text("brief")
    plan = {
        "levers": [{"lever": "uno"}, {"lever": "due"}, {"lever": "tre"}],
        "assets": ["acqua"],
        "excluded": ["gradiente", "ombra", "lente"],
        "applications": [{"name": "insegna", "size": "16 mm"}, {"name": "app", "size": "32 px"}],
    }
    real_open = context.ledger.open

    def open_then_die_on_b(spec: TicketSpec, *args: object, **kwargs: object) -> str:
        ticket = real_open(spec, *args, **kwargs)  # type: ignore[arg-type]
        if spec.assignee == "direction-b":
            raise KeyboardInterrupt
        return ticket

    with monkeypatch.context() as patch:
        patch.setattr(context.ledger, "open", open_then_die_on_b)
        with pytest.raises(KeyboardInterrupt):
            box.call("t1", "plan_exploration", plan)
    context.finished = None

    result = box.call("t1", "plan_exploration", plan)

    assert not result.get("is_error"), result["content"]
    tickets = context.ledger.children(root)
    assert len(tickets) == 3  # no direction was opened twice
    rows = context.ledger.concepts("p", 1)
    assert sorted(row.idea_ticket for row in rows) == sorted(tickets)
    assert [row.letter for row in rows] == ["a", "b", "c"]


def delivered_note_box(tmp_path: Path) -> tuple[Toolbox, ToolContext, str]:
    """A delivered ticket the director opened, and the director's toolbox with accept and rework."""
    spec = TicketSpec(
        title="Nota",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="copywriter",
        outputs=["nota.md"],
        checks={"*.md": ["req:letta"]},
        media=[Medium.NONE],
        medium_why="solo un testo di prova",
    )
    box, context, ticket = closing_box(tmp_path, spec, "design-director", "accept_ticket", "rework_ticket")
    context.ticket_id = context.ledger.open(
        DIRECTOR, "p"
    )  # the director works on its own ticket, not the child
    work = tmp_path / "work"
    (work / "nota.md").write_text("v1")
    digest = sha256_under(work, "nota.md")
    context.ledger.add_evidence(
        EvidenceEntry(
            at="2026-01-01T00:00:00+00:00",
            project="p",
            file="nota.md",
            sha256=digest,
            check_name="req:letta",
            result="PASS",
            signer="copywriter",
            ticket_id=ticket,
        )
    )
    context.ledger.apply(ticket, Action.DELIVER, "copywriter", "fatto", None, {"nota.md": digest})
    return box, context, ticket


@pytest.mark.parametrize(
    ("name", "note", "status", "action"),
    [
        ("accept_ticket", "ok", Status.ACCEPTED, "accept"),
        ("rework_ticket", "cambia il titolo", Status.REWORK, "rework"),
    ],
)
def test_a_replayed_accept_or_rework_returns_its_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, note: str, status: Status, action: str
) -> None:
    box, context, ticket = delivered_note_box(tmp_path)
    arguments = {"ticket": ticket, "note": note}
    crash_after_the_transition(box, context, monkeypatch, name, arguments)
    assert context.ledger.status(ticket)[0] is status

    result = box.call("t1", name, arguments)

    assert not result.get("is_error"), result["content"]
    assert json.loads(result["content"]) == {"ok": True, "status": status.value}
    assert [event.action for event in context.ledger.history(ticket)].count(action) == 1
    intact(context.ledger)


def test_a_ticket_in_the_target_state_replays_only_its_own_last_action(tmp_path: Path) -> None:
    """The ledger's rule still holds when the ticket is in the target state for another reason."""
    box, context, ticket = delivered_note_box(tmp_path)
    assert not box.call("t1", "accept_ticket", {"ticket": ticket, "note": "ok"}).get("is_error")
    context.ledger.apply(ticket, Action.REWORK, "design-director", "cambia")  # last event: a rework

    result = box.call("t2", "rework_ticket", {"ticket": ticket, "note": "ancora una volta"})
    assert not result.get("is_error"), result["content"]  # the same actor repeating its last action
    result = box.call("t3", "accept_ticket", {"ticket": ticket, "note": "ok"})
    assert result.get("is_error")  # a rework state is not accepted
    assert "non è ammesso" in result["content"]
