"""The agent loop with recorded answers: budget, interruptions, cut and refused answers, fallbacks and
reminders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agency.agents.loop import CLOSING, AgentRunner, _after_fallback
from agency.agents.toolbox import TOOLS, Toolbox, tools_for
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import REPO_ROOT, Settings
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.phase import DirectorMode
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Status, TicketSpec, TicketType
from agency.gateway import BudgetExceeded, ModelGateway
from agency.ledger import Ledger
from agency.workshop.craft import CommandIndex
from support.flow import DIRECTOR, bare_context, needs_craft, production_spec, runner, use
from support.rules import RULES
from support.scripted import ScriptedTransport, turn
from support.settings import settings


@needs_craft
def test_budget_stop_keeps_the_work_and_resumes_after_an_increase(tmp_path: Path) -> None:
    config = settings(tmp_path)
    responses = [turn(use("list_files", "t1")), turn(use("block", "t2", reason="prova finita"))]
    run, transport, ledger = runner(config, responses)
    ledger.set_project("p", 0.0003)
    ticket = ledger.open(production_spec(), "p")
    with pytest.raises(BudgetExceeded):
        run.run(ticket)
    assert ledger.status(ticket)[0] is Status.OPEN  # not blocked: it waits for the client's choice
    ledger.set_budget("p", 1.0)
    assert run.run(ticket).state == "blocked"
    assert transport.requests[-1]["messages"][0]["content"].startswith("Scrivi note")


def test_interruption_resumes_without_repeating_effects(tmp_path: Path) -> None:
    config = settings(tmp_path)
    (config.projects_dir / "p/work").mkdir(parents=True)

    class Dies(ScriptedTransport):
        def stream(self, params: dict) -> dict:
            if not self.responses:
                raise ConnectionError("process killed")
            return super().stream(params)

    ledger = Ledger(config.layout.ledger)
    ledger.set_project("p", 25.0)
    spec = TicketSpec(
        title="Piano",
        request="r",
        type=TicketType.DELIVERY,
        sender="router",
        assignee="design-director",
        outputs=["exports/a.svg"],
        checks={"*.svg": ["svg_audit"]},
    )
    root = ledger.open(spec, "p")
    child = {
        "title": "Segno",
        "request": "r",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": ["source/s.vectorcraft"],
        "checks": {"*.vectorcraft": ["master_open"]},
        "media": ["vettoriale"],
    }
    dying = Dies([turn(use("open_ticket", "t1", **child))])
    index = CommandIndex([])
    first = AgentRunner(
        ModelGateway(dying, ledger, config),
        ledger,
        config,
        index,
        FileStore(config.layout.artifacts),
        rules=RULES,
    )
    with pytest.raises(ConnectionError):
        first.run(root)
    assert len(ledger.children(root)) == 1
    # It restarts from the transcript: no call repeated, no ticket opened twice.
    again = ScriptedTransport([turn(use("hand_off", "t2", note="attendo il segno"))])
    second = AgentRunner(
        ModelGateway(again, ledger, config),
        ledger,
        config,
        index,
        FileStore(config.layout.artifacts),
        rules=RULES,
    )
    assert second.run(root).state == "handed_off"
    assert len(ledger.children(root)) == 1
    assert len(again.requests) == 1
    sent = again.requests[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]


def test_interrupted_between_response_and_tools_does_not_duplicate(tmp_path: Path) -> None:
    config = settings(tmp_path)
    (config.projects_dir / "p/work").mkdir(parents=True)
    ledger = Ledger(config.layout.ledger)
    ledger.set_project("p", 25.0)
    root = ledger.open(
        TicketSpec(
            title="Piano",
            request="r",
            type=TicketType.DELIVERY,
            sender="router",
            assignee="design-director",
            outputs=["exports/a.svg"],
            checks={"*.svg": ["svg_audit"]},
        ),
        "p",
    )
    child = {
        "title": "Segno",
        "request": "r",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": ["source/s.vectorcraft"],
        "checks": {"*.vectorcraft": ["master_open"]},
        "media": ["vettoriale"],
    }
    transcript = Transcript(config.data_dir / "runs/p" / f"{root}-a1.jsonl")
    transcript.append({"role": "user", "content": "piano"})
    transcript.append({"role": "assistant", "content": [use("open_ticket", "t1", **child)]})
    ledger.open(
        TicketSpec.model_validate(child | {"sender": "design-director", "parent": root}),
        "p",
        operation=(f"{root}-a1:t1", f"{root}-a1", "open_ticket"),
    )
    again = ScriptedTransport([turn(use("hand_off", "t2", note="attendo il segno"))])
    runner_ = AgentRunner(
        ModelGateway(again, ledger, config),
        ledger,
        config,
        CommandIndex([]),
        FileStore(config.layout.artifacts),
        rules=RULES,
    )
    assert runner_.run(root).state == "handed_off"
    assert len(ledger.children(root)) == 1


@needs_craft
def test_finished_instance_is_not_run_again(tmp_path: Path) -> None:
    config = settings(tmp_path)
    run, transport, ledger = runner(config, [])
    ticket = ledger.open(production_spec(), "p")
    done = Outcome(state=OutcomeState.DELIVERED, note="x")
    Transcript(config.data_dir / "runs/p" / f"{ticket}-a1.jsonl").finish(done)
    assert run.run(ticket).state == "delivered"
    assert transport.requests == []


@needs_craft
def test_refusal_blocks_the_ticket(tmp_path: Path) -> None:
    config = settings(tmp_path)
    reply = turn(stop="refusal") | {"stop_details": {"category": "cyber"}}
    run, _, ledger = runner(config, [reply])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"


@needs_craft
def test_truncated_response_is_not_added_to_history(tmp_path: Path) -> None:
    config = settings(tmp_path)
    partial = turn(use("list_files", "t1"), stop="max_tokens")
    run, transport, ledger = runner(config, [partial, turn(use("block", "t2", reason="manca il brief"))])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"
    assert transport.requests[1]["max_tokens"] == 128000
    assert len(transport.requests[1]["messages"]) == 1


def _assistant_turns(config: Settings, ticket: str) -> list[dict]:
    entries = Transcript(config.layout.transcript(ProjectName("p"), f"{ticket}-a1")).entries()
    return [entry for entry in entries if entry.get("message", {}).get("role") == "assistant"]


@needs_craft
def test_a_context_window_cut_blocks_without_appending(tmp_path: Path) -> None:
    config = settings(tmp_path)
    cut = turn(use("list_files", "t1"), stop="model_context_window_exceeded")
    run, transport, ledger = runner(config, [cut, turn(use("block", "t2", reason="non deve arrivare"))])
    ticket = ledger.open(production_spec(), "p")
    outcome = run.run(ticket)
    assert outcome.state == "blocked"
    assert outcome.note == "risposta troncata dalla finestra di contesto"
    assert ledger.status(ticket)[0] == Status.BLOCKED
    assert len(transport.requests) == 1  # a full window does not shrink on a retry
    assert _assistant_turns(config, ticket) == []
    entries = Transcript(config.layout.transcript(ProjectName("p"), f"{ticket}-a1")).entries()
    assert [entry.get("message", {}).get("role") for entry in entries if "message" in entry] == ["user"]


@needs_craft
@pytest.mark.parametrize("stop", ["end_turn", "stop_sequence"])
def test_a_tool_call_is_never_appended_without_its_result(tmp_path: Path, stop: str) -> None:
    config = settings(tmp_path)
    odd = turn(use("block", "t1", reason="non deve girare"), stop=stop)
    run, transport, ledger = runner(config, [odd, turn(use("block", "t2", reason="non deve arrivare"))])
    ticket = ledger.open(production_spec(), "p")
    outcome = run.run(ticket)
    assert outcome.state == "blocked"
    assert outcome.note == f"risposta interrotta ({stop}) con uno strumento senza risultato"
    assert ledger.status(ticket)[0] == Status.BLOCKED
    assert len(transport.requests) == 1
    assert _assistant_turns(config, ticket) == []
    assert "non deve girare" not in str(ledger.history(ticket))  # the tool did not run


@needs_craft
def test_each_answer_in_the_transcript_names_its_request_and_a_truncated_one_is_not_there(
    tmp_path: Path,
) -> None:
    """The replay view matches each turn to its call through this request_id."""
    config = settings(tmp_path)
    partial = turn(use("list_files", "t1"), stop="max_tokens") | {"_request_id": "req_tagliata"}
    final = turn(use("block", "t2", reason="manca il brief")) | {"_request_id": "req_blocco"}
    run, _, ledger = runner(config, [partial, final])
    ticket = ledger.open(production_spec(), "p")
    run.run(ticket)
    entries = Transcript(config.layout.transcript(ProjectName("p"), f"{ticket}-a1")).entries()
    answers = [entry for entry in entries if entry.get("message", {}).get("role") == "assistant"]
    assert [entry.get("request_id") for entry in answers] == ["req_blocco"]


FALLBACK = {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-5"}}


@needs_craft
def test_the_unanswered_tool_guard_looks_only_at_the_kept_content(tmp_path: Path) -> None:
    """A declined attempt's tool call is dropped, so a finished answer after it is not an interrupted one."""
    config = settings(tmp_path)
    declined = use("block", "tA", reason="scelto dal tentativo respinto")
    text = {"type": "text", "text": "ho finito"}
    done = turn(declined, FALLBACK, text, stop="end_turn")
    run, transport, ledger = runner(config, [done, turn(use("block", "t2", reason="manca il brief"))])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).note == "manca il brief"
    assert len(transport.requests) == 2


@needs_craft
def test_tool_calls_before_a_fallback_are_not_executed(tmp_path: Path) -> None:
    """The declined attempt's `block` must not close the ticket: only the serving model's call runs."""
    config = settings(tmp_path)
    declined = use("block", "tA", reason="scelto dal tentativo respinto")
    text = {"type": "text", "text": "continuo"}
    content = [declined, FALLBACK, text, use("list_files", "tB")]
    closing = turn(use("block", "t2", reason="manca il brief"))
    run, transport, ledger = runner(config, [turn(*content), closing])
    ticket = ledger.open(production_spec(), "p")
    outcome = run.run(ticket)
    assert outcome.note == "manca il brief"  # A would have closed the ticket with its own reason
    assert len(transport.requests) == 2
    served = [FALLBACK, text, use("list_files", "tB")]
    history = transport.requests[1]["messages"]
    assert history[1] == {"role": "assistant", "content": served}
    assert [block["tool_use_id"] for block in history[2]["content"]] == ["tB"]
    entries = Transcript(config.layout.transcript(ProjectName("p"), f"{ticket}-a1")).entries()
    answers = [entry for entry in entries if entry.get("message", {}).get("role") == "assistant"]
    assert answers[0]["message"]["content"] == served
    assert answers[0]["raw"] == content
    assert "raw" not in answers[1]


def test_a_fallback_keeps_only_what_the_serving_model_continues_from() -> None:
    other = {"type": "fallback", "from": {"model": "claude-opus-5"}, "to": {"model": "claude-opus-4-8"}}
    paired = {"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {}}
    result = {"type": "web_search_tool_result", "tool_use_id": "s1", "content": []}
    unpaired = {"type": "server_tool_use", "id": "s2", "name": "web_search", "input": {}}
    text = {"type": "text", "text": "parziale"}
    after = [
        {"type": "thinking", "thinking": "", "signature": "x"},
        use("list_files", "tB"),
        {"type": "mystery", "x": 1},
        unpaired,
    ]
    before = [
        {"type": "thinking", "thinking": "", "signature": "x"},
        {"type": "redacted_thinking", "data": "x"},
        use("block", "tA", reason="no"),
        paired,
        result,
        unpaired,
        {"type": "mystery", "x": 1},
        text,
        FALLBACK,
        use("block", "tC", reason="no"),
        other,
    ]
    assert _after_fallback([*before, *after]) == [paired, result, text, FALLBACK, other, *after]
    plain = [{"type": "thinking", "thinking": "", "signature": "x"}, use("list_files", "tB"), unpaired]
    assert _after_fallback(plain) == plain


@needs_craft
def test_agent_ending_without_delivery_is_reminded_then_blocked(tmp_path: Path) -> None:
    config = settings(tmp_path)
    text = {"type": "text", "text": "fatto"}
    run, transport, ledger = runner(config, [turn(text, stop="end_turn"), turn(text, stop="end_turn")])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"
    assert len(transport.requests) == 2


@needs_craft
def test_each_role_sends_its_registry_model_and_effort(tmp_path: Path) -> None:
    """With no client choice, each role's first request carries its own row of registry/roles.json."""
    registry = json.loads((REPO_ROOT / "registry/roles.json").read_text(encoding="utf-8"))["roles"]
    roles = ["critic", "design-director", "identity-designer", "qa-inspector"]
    config = settings(tmp_path)
    blocks = [turn(use("block", f"t{n}", reason="basta la prima richiesta")) for n in range(len(roles))]
    run, transport, ledger = runner(config, blocks)
    choice = ledger.project("p")
    assert choice is not None and (choice.model, choice.effort) == ("", "")  # the client chose nothing

    sent = {}
    for role in roles:
        ticket = ledger.open(production_spec().model_copy(update={"assignee": role}), "p")
        assert run.run(ticket).state == "blocked"
        first = transport.requests[-1]
        sent[role] = (first["model"], first["output_config"]["effort"])

    assert sent == {role: (registry[role]["model"], registry[role]["effort"]) for role in roles}
    # Without this the test could not tell the registry from one constant model and effort.
    assert len({model for model, _ in sent.values()}) > 1
    assert len({effort for _, effort in sent.values()}) > 1


REMINDER = "Non hai concluso il ticket. Chiudi con uno di questi strumenti: "


SKETCH = production_spec().model_copy(update={"type": TicketType.SKETCH})


PROPOSAL = production_spec().model_copy(update={"type": TicketType.PROPOSAL})


BOARD = production_spec().model_copy(update={"assignee": "critic", "prompt": "critic-board"})


@pytest.mark.parametrize(
    ("role", "spec", "mode", "closers"),
    [
        ("identity-designer", production_spec(), None, "deliver, block"),
        ("design-director", DIRECTOR, None, "deliver, hand_off, block"),
        ("direction-a", SKETCH, None, "submit_concept, block"),
        ("direction-a", PROPOSAL, None, "deliver, block"),
        ("design-director", DIRECTOR, "plan", "plan_exploration, block"),
        ("design-director", DIRECTOR, "select", "select_concepts, block"),
        ("design-director", DIRECTOR, "present", "draft_presentation, present_concepts, block"),
        ("critic", BOARD, None, "deliver, block"),
    ],
    ids=["author", "director", "explore", "proposal", "plan", "select", "present", "board"],
)
def test_the_reminder_names_each_phase_closing_tools(
    tmp_path: Path, role: str, spec: TicketSpec, mode: DirectorMode | None, closers: str
) -> None:
    """The nudge after a turn that closed nothing names only this phase's closing tools, in a fixed order."""
    box = Toolbox(bare_context(tmp_path, role), tools_for(RULES, role, spec, mode))
    if mode is None and role == "design-director":
        assert "reject_concept" in box.tools  # it closes, yet the reminder leaves it out
    assert AgentRunner._reminder(box) == f"{REMINDER}{closers}."


RESUMED = "ripreso dopo un'interruzione"


CHOSEN = {"chosen": ["A"], "reasons": "r"}


NONE_CHOSEN = {"chosen": [], "reasons": "r"}


PAGES = {"pagine": ["presentazione/pagina-1.png"], "poi": "guarda"}


PRESENTED = {
    "proposals": [{"letter": "A", "title": "t", "idea": "i", "why": "w", "risk": "r"}],
    "recommended": "A",
    "reasons": "r",
}


NONE_PRESENTED = {"proposals": [], "recommended": None, "reasons": "r"}


RESTORED = [
    ("deliver", {"ok": True, "status": "delivered"}, OutcomeState.DELIVERED, RESUMED),
    ("block", {"ok": True, "status": "blocked"}, OutcomeState.BLOCKED, RESUMED),
    ("hand_off", {"ok": True, "waiting": ["T-0002"]}, OutcomeState.HANDED_OFF, RESUMED),
    ("plan_exploration", {"ok": True, "tickets": ["T-0002"]}, OutcomeState.HANDED_OFF, RESUMED),
    ("submit_concept", {"ok": True}, OutcomeState.DELIVERED, RESUMED),
    ("reject_concept", {"ok": True}, OutcomeState.CONCEPT_REJECTED, RESUMED),
    ("select_concepts", CHOSEN, OutcomeState.SELECTED, None),
    ("select_concepts", NONE_CHOSEN, OutcomeState.NO_CONCEPT, None),
    ("draft_presentation", PAGES, None, None),
    ("draft_presentation", NONE_PRESENTED, OutcomeState.NO_CONCEPT, None),
    ("present_concepts", PRESENTED, OutcomeState.PRESENTED, None),
    ("present_concepts", NONE_PRESENTED, OutcomeState.NO_CONCEPT, None),
    ("write_file", {"ok": True}, None, None),
]


@pytest.mark.parametrize(
    ("name", "stored", "state", "note"),
    RESTORED,
    ids=[
        "deliver",
        "block",
        "hand_off",
        "plan_exploration",
        "submit_concept",
        "reject_concept",
        "select_concepts-chosen",
        "select_concepts-none",
        "draft_presentation-pages",
        "draft_presentation-none",
        "present_concepts-chosen",
        "present_concepts-none",
        "write_file-not-closing",
    ],
)
def test_restore_closes_each_closing_tool_with_its_state(
    tmp_path: Path, name: str, stored: dict, state: OutcomeState | None, note: str | None
) -> None:
    """On resume a recorded effect is not run again: its stored result comes back and closes as before.

    `state` None: the instance stays open. `note` None: the stored result itself is the note.
    """
    context = bare_context(tmp_path, "design-director")
    text = json.dumps(stored, ensure_ascii=False)
    context.ledger.record_operation("i:t1", "i", name, text)

    result = Toolbox(context, [TOOLS[name]]).call("t1", name, {})

    assert result == {"type": "tool_result", "tool_use_id": "t1", "content": text}
    expected = None if state is None else Outcome(state=state, note=text if note is None else note)
    assert context.finished == expected


def test_the_reminder_offers_every_closing_tool_but_reject_concept() -> None:
    """The reminder's list and the resume table answer different questions, so they stay apart (SIM-010).
    They must still name the same closing tools, but for reject_concept: a closing tool added to one and not
    to the other fails here."""
    closes_on_resume = {name for name, _, state, _ in RESTORED if state is not None}
    assert {name for name, tool in TOOLS.items() if tool.closes is not None} <= closes_on_resume
    assert set(CLOSING) == closes_on_resume - {"reject_concept"}


@needs_craft
def test_history_is_append_only_between_calls(tmp_path: Path) -> None:
    config = settings(tmp_path)
    responses = [
        turn(use("list_files", "t1")),
        turn(use("list_files", "t2")),
        turn(use("block", "t3", reason="manca il brief")),
    ]
    run, transport, ledger = runner(config, responses)
    ticket = ledger.open(production_spec(), "p")
    run.run(ticket)
    first, second, third = [r["messages"] for r in transport.requests]
    assert second[: len(first)] == first and third[: len(second)] == second
    assert transport.requests[0]["tools"] == transport.requests[2]["tools"]
    assert transport.requests[0]["system"] == transport.requests[2]["system"]
