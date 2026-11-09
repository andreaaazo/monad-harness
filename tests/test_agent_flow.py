"""Il percorso completo con risposte registrate e Craft veri: nessuna chiamata all'API."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import threading
import time
import tracemalloc
from pathlib import Path, PurePosixPath

import pytest
from PIL import Image

from agency.agents.loop import AgentRunner, _after_fallback
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import REPO_ROOT, Settings
from agency.contracts import phase
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, Status, TicketSpec, TicketType, Verdict
from agency.gateway import BudgetExceeded, ModelGateway, ScriptedTransport
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow
from agency.runtime import open_session
from agency.tools import craft, master
from agency.tools.craft import Command, CommandIndex
from agency.tools.sandbox import JOB, MEMORY_MAX_BYTES, TASKS_MAX, Completed, Sandbox, SandboxUnavailable
from agency.tools.surface import TOOLS, Toolbox, ToolContext, tools_for

SVG_PATH = "M10 90 L50 10 L90 90 Z"
needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def use(name: str, tool_id: str, **arguments: object) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def turn(*blocks: dict, stop: str = "tool_use") -> dict:
    return {
        "content": list(blocks),
        "stop_reason": stop,
        "model": "claude-opus-5-5",
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


def settings(tmp_path: Path, **extra: float) -> Settings:
    return Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "projects", _env_file=None, **extra)  # type: ignore[call-arg]


def production_spec() -> TicketSpec:
    return TicketSpec(
        title="Segno",
        request="Disegna il segno",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=["source/segno.vectorcraft", "exports/segno.svg"],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
    )


def runner(config: Settings, responses: list[dict]) -> tuple[AgentRunner, ScriptedTransport, Ledger]:
    """Il progetto `p` con il tetto che il cliente dichiarerebbe: senza, il gateway non spende (ADR-0043)."""
    ledger = Ledger(config.ledger_path)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(responses)
    index = CommandIndex.load(config.data_dir / "craft-index")
    return (
        AgentRunner(
            ModelGateway(transport, ledger, config), ledger, config, index, FileStore(config.artifacts_dir)
        ),
        transport,
        ledger,
    )


def steps() -> list[dict]:
    return [
        {"command": "path.create", "params": {"d": SVG_PATH}},
        {"command": "select.set", "params": {"ids": [2]}},
        {"command": "paint.setStroke", "params": {"none": True}},
        {"command": "paint.setFill", "params": {"color": "#111111"}},
    ]


@needs_craft
def test_author_cannot_deliver_without_master_then_can(tmp_path: Path) -> None:
    config = settings(tmp_path)
    responses = [
        turn(use("deliver", "t1", note="fatto", verdict=None)),
        turn(use("craft_run", "t2", document="source/segno.vectorcraft", steps=steps())),
        turn(use("export_master", "t3", master="source/segno.vectorcraft", output="exports/segno.svg")),
        turn(
            use("run_check", "t4", check="master_open", file="source/segno.vectorcraft"),
            use("run_check", "t5", check="svg_audit", file="exports/segno.svg"),
        ),
        turn(use("deliver", "t6", note="master e svg", verdict=None)),
    ]
    run, transport, ledger = runner(config, responses)
    ticket = ledger.open(production_spec(), "p")
    outcome = run.run(ticket)
    assert outcome.state == "delivered"
    assert ledger.status(ticket)[0] is Status.DELIVERED
    refused = transport.requests[1]["messages"][-1]["content"][0]
    assert refused["is_error"] and "consegna rifiutata" in refused["content"]
    assert {r.signer for r in ledger.evidence("p")} == {"identity-designer"}


def test_schemas_have_no_identity_field(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "identity-designer",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    text = json.dumps(Toolbox(context).definitions())
    for field in ('"by"', '"actor"', '"signer"', '"from"', '"sender"'):
        assert field not in text


def test_role_cannot_use_tools_outside_its_set(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    result = Toolbox(context).call("x", "craft_run", {"document": "a.vectorcraft", "steps": []})
    assert result["is_error"]


def test_reviewer_writes_only_reports(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    box = Toolbox(context)
    assert box.call("a", "write_file", {"path": "source/note.md", "content": "x"})["is_error"]
    assert not box.call("b", "write_file", {"path": "reviews/r.md", "content": "x"}).get("is_error")


def test_author_cannot_write_vectors_by_hand(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "identity-designer",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    result = Toolbox(context).call("a", "write_file", {"path": "exports/a.svg", "content": "<svg/>"})
    assert result["is_error"]


def test_path_outside_the_job_is_refused(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    assert Toolbox(context).call("a", "read_file", {"path": "../../etc/passwd"})["is_error"]


def test_budget_stop_keeps_the_work_and_resumes_after_an_increase(tmp_path: Path) -> None:
    config = settings(tmp_path)
    responses = [turn(use("list_files", "t1")), turn(use("block", "t2", reason="prova finita"))]
    run, transport, ledger = runner(config, responses)
    ledger.set_project("p", 0.0003)
    ticket = ledger.open(production_spec(), "p")
    with pytest.raises(BudgetExceeded):
        run.run(ticket)
    assert ledger.status(ticket)[0] is Status.OPEN  # non è bloccato: aspetta la scelta del cliente
    ledger.set_budget("p", 1.0)
    assert run.run(ticket).state == "blocked"
    assert transport.requests[-1]["messages"][0]["content"].startswith("Scrivi note")


def test_interruption_resumes_without_repeating_effects(tmp_path: Path) -> None:
    config = settings(tmp_path)
    (config.projects_dir / "p/work").mkdir(parents=True)

    class Dies(ScriptedTransport):
        def stream(self, params: dict) -> dict:
            if not self.responses:
                raise ConnectionError("processo ucciso")
            return super().stream(params)

    ledger = Ledger(config.ledger_path)
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
        ModelGateway(dying, ledger, config), ledger, config, index, FileStore(config.artifacts_dir)
    )
    with pytest.raises(ConnectionError):
        first.run(root)
    assert len(ledger.children(root)) == 1
    # Riparte dalla trascrizione: nessuna chiamata ripetuta, nessun ticket doppio.
    again = ScriptedTransport([turn(use("hand_off", "t2", note="attendo il segno"))])
    second = AgentRunner(
        ModelGateway(again, ledger, config), ledger, config, index, FileStore(config.artifacts_dir)
    )
    assert second.run(root).state == "handed_off"
    assert len(ledger.children(root)) == 1
    assert len(again.requests) == 1
    sent = again.requests[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]


def test_interrupted_between_response_and_tools_does_not_duplicate(tmp_path: Path) -> None:
    config = settings(tmp_path)
    (config.projects_dir / "p/work").mkdir(parents=True)
    ledger = Ledger(config.ledger_path)
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
        ModelGateway(again, ledger, config), ledger, config, CommandIndex([]), FileStore(config.artifacts_dir)
    )
    assert runner_.run(root).state == "handed_off"
    assert len(ledger.children(root)) == 1


def test_finished_instance_is_not_run_again(tmp_path: Path) -> None:
    config = settings(tmp_path)
    run, transport, ledger = runner(config, [])
    ticket = ledger.open(production_spec(), "p")
    done = Outcome(state=OutcomeState.DELIVERED, note="x")
    Transcript(config.data_dir / "runs/p" / f"{ticket}-a1.jsonl").finish(done)
    assert run.run(ticket).state == "delivered"
    assert transport.requests == []


def test_refusal_blocks_the_ticket(tmp_path: Path) -> None:
    config = settings(tmp_path)
    reply = turn(stop="refusal") | {"stop_details": {"category": "cyber"}}
    run, _, ledger = runner(config, [reply])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"


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


def test_each_answer_in_the_transcript_names_its_request_and_a_truncated_one_is_not_there(
    tmp_path: Path,
) -> None:
    """Il Replay lega ogni turno alla sua chiamata con questo request_id."""
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


def test_agent_ending_without_delivery_is_reminded_then_blocked(tmp_path: Path) -> None:
    config = settings(tmp_path)
    text = {"type": "text", "text": "fatto"}
    run, transport, ledger = runner(config, [turn(text, stop="end_turn"), turn(text, stop="end_turn")])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"
    assert len(transport.requests) == 2


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
DIRECTOR = production_spec().model_copy(update={"assignee": "design-director"})


def bare_context(tmp_path: Path, role: str) -> ToolContext:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    artifacts = FileStore(tmp_path / "artifacts")
    inputs = config.layout.ops_inputs("p", "i")
    inputs.mkdir(parents=True, exist_ok=True)
    sandbox = Sandbox(tmp_path, ops=inputs)
    return ToolContext(role, "p", "T-1", "i", ledger, sandbox, CommandIndex([]), artifacts)


@pytest.mark.parametrize(
    ("role", "spec", "mode", "closers"),
    [
        ("identity-designer", production_spec(), "", "deliver, block"),
        ("design-director", DIRECTOR, "", "deliver, hand_off, block"),
        ("direction-a", SKETCH, "", "submit_concept, block"),
        ("direction-a", PROPOSAL, "", "deliver, block"),
        ("design-director", DIRECTOR, "plan", "plan_exploration, block"),
        ("design-director", DIRECTOR, "select", "select_concepts, block"),
        ("design-director", DIRECTOR, "present", "draft_presentation, present_concepts, block"),
        ("critic", BOARD, "", "deliver, block"),
    ],
    ids=["author", "director", "explore", "proposal", "plan", "select", "present", "board"],
)
def test_the_reminder_names_each_phase_closing_tools(
    tmp_path: Path, role: str, spec: TicketSpec, mode: str, closers: str
) -> None:
    """The nudge after a turn that closed nothing names only this phase's closing tools, in a fixed order."""
    box = Toolbox(bare_context(tmp_path, role), tools_for(role, spec, mode))
    if mode == "" and role == "design-director":
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


def test_observe_needs_a_render_really_viewed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    ledger = Ledger(config.ledger_path)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic", "p", ticket, "i", ledger, Sandbox(work), CommandIndex([]), FileStore(tmp_path / "artifacts")
    )
    box = Toolbox(context)
    seen = "Quadrato rosso pieno, bordi netti, nessun difetto visibile nel render."
    arguments = {"file": "a.png", "seen": seen}
    assert box.call("a", "observe", arguments)["is_error"]
    proof = json.loads(box.call("b", "render", {"path": "a.png"})["content"])["proofs"][0]
    assert box.call("c", "observe", arguments)["is_error"]
    box.call("d", "view_image", {"path": proof})
    assert not box.call("e", "observe", arguments).get("is_error")


def critic_box(tmp_path: Path) -> tuple[Toolbox, Path]:
    """A critic on a real ticket, with its own work folder."""
    work = tmp_path / "work"
    work.mkdir()
    ledger = Ledger(settings(tmp_path).ledger_path)
    ticket = ledger.open(production_spec(), "p")
    artifacts = FileStore(tmp_path / "artifacts")
    context = ToolContext("critic", "p", ticket, "i", ledger, Sandbox(work), CommandIndex([]), artifacts)
    return Toolbox(context), work


def rendered(box: Toolbox, tool_id: str, path: str, zooms: list[list[float]] | None = None) -> list[str]:
    result = box.call(tool_id, "render", {"path": path, "zooms": zooms or []})
    proofs: list[str] = json.loads(result["content"])["proofs"]
    return proofs


SEEN_RED = "Quadrato rosso pieno, bordi netti, nessun difetto visibile nel render."


def test_observe_refuses_a_render_viewed_for_an_older_version(tmp_path: Path) -> None:
    """The critic viewed the red version's render. The black version was rendered and never viewed."""
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    (proof,) = rendered(box, "r1", "a.png")
    box.call("v1", "view_image", {"path": proof})
    Image.new("RGB", (100, 100), (0, 0, 0)).save(work / "a.png")
    rendered(box, "r2", "a.png")

    result = box.call("o1", "observe", {"file": "a.png", "seen": SEEN_RED})

    assert result.get("is_error")
    assert "non hai guardato un render della versione attuale" in str(result["content"])


def test_same_stem_sources_get_distinct_proofs(tmp_path: Path) -> None:
    """Each source has its own proof, so viewing x.jpg's render cannot back evidence for x.png."""
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "x.png")
    Image.new("RGB", (100, 100), (30, 30, 200)).save(work / "x.jpg")
    png = rendered(box, "r1", "x.png")
    jpg = rendered(box, "r2", "x.jpg")
    box.call("v1", "view_image", {"path": jpg[0]})

    assert png != jpg
    assert box.call("o1", "observe", {"file": "x.png", "seen": SEEN_RED}).get("is_error")


def test_two_zooms_with_one_corner_get_two_files(tmp_path: Path) -> None:
    from PIL import Image

    box, work = critic_box(tmp_path)
    Image.new("RGB", (400, 400), (200, 30, 30)).save(work / "a.png")

    proofs = rendered(box, "r1", "a.png", zooms=[[0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.8, 0.8]])

    assert len(proofs) == 3 and len(set(proofs)) == 3
    with Image.open(work / proofs[1]) as small, Image.open(work / proofs[2]) as large:
        assert small.size == (40, 40)
        assert large.size == (320, 320)


def test_compute_runs_the_script_and_returns_exit_and_output(tmp_path: Path) -> None:
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    result = box.call("c1", "compute", {"code": "print(6 * 7)"})
    assert json.loads(result["content"]) == {"exit": 0, "output": "42\n"}


class CountingSandbox(Sandbox):
    """Plays `vectorcraft-cli run`: writes the exported document and prints one result per command."""

    def __init__(self, work: Path, ops: Path) -> None:
        super().__init__(work, ops=ops)
        self.calls: list[list[str]] = []

    def run(self, command: list[str], timeout: float = 120, stdin: str | None = None) -> Completed:
        self.calls.append(command)
        export = Path(command[command.index("--export") + 1]).relative_to(JOB)
        (self.work / export).write_text("documento costruito", encoding="utf-8")
        lines = [json.dumps({"step": "cmd", "result": {"id": 2}}), json.dumps({"step": "open"}), "non json"]
        return Completed(0, "\n".join(lines), "")


def harness_folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The work folder, and the harness folders outside it: inputs bound at /ops, and records (ADR-0044)."""
    layout = settings(tmp_path).layout
    work = tmp_path / "work"
    work.mkdir()
    inputs = layout.ops_inputs("p", "i")
    inputs.mkdir(parents=True)
    return work, inputs, layout.ops_records("p", "i")


def test_craft_run_replays_its_stored_result_on_resume(tmp_path: Path) -> None:
    """The steps run once. A second call with the same operation id copies the built document again."""
    work, inputs, records = harness_folders(tmp_path)
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"
    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    (work / master).unlink()  # the copy the crash, or a later edit, took away

    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"


def test_compute_script_lives_outside_the_work_folder(tmp_path: Path) -> None:
    """The agent's compute script lives in /ops, bound read-only, and /job has no `.ops` (SEC-001, ADR-0044).

    The sandboxed code can neither rewrite its own script nor leave a file in /ops for the harness to find.
    """
    config = settings(tmp_path)
    probe = (
        "import errno, os, sys\n"
        "print(sys.argv[0])\n"
        "print(os.path.exists('/job/.ops'))\n"
        "for path in (sys.argv[0], '/ops/x'):\n"
        "    try:\n"
        "        open(path, 'a').close()\n"
        "        print('written')\n"
        "    except OSError as error:\n"
        "        print(errno.errorcode[error.errno])\n"
    )
    ledger = Ledger(config.ledger_path)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(
        [turn(use("compute", "c1", code=probe)), turn(use("block", "c2", reason="prova finita"))]
    )
    gateway = ModelGateway(transport, ledger, config)
    run = AgentRunner(gateway, ledger, config, CommandIndex([]), FileStore(config.artifacts_dir))
    ticket = ledger.open(production_spec(), "p")

    run.run(ticket)

    result = json.loads(transport.requests[1]["messages"][-1]["content"][0]["content"])
    script, *seen = result["output"].split()
    assert seen == ["False", "EROFS", "EROFS"]
    assert PurePosixPath(script).parent == PurePosixPath("/ops")
    inputs = config.layout.ops_inputs("p", phase.instance(ticket, 1))
    assert (inputs / PurePosixPath(script).name).read_text(encoding="utf-8") == probe
    assert not (inputs / "x").exists()
    assert not (config.project_dir(ProjectName("p")) / "work" / ".ops").exists()


def test_craft_run_resume_reads_only_the_harness_record(tmp_path: Path) -> None:
    """Whatever sandboxed code writes into /job is never read on resume: not at the old `.ops` place, not over
    the partial export. The record is the harness's copy, outside any sandbox (SEC-001, ADR-0044)."""
    work, inputs, records = harness_folders(tmp_path)
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"
    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    for forged in (".ops/op1.result.json", ".ops/op1.vectorcraft", ".partial/op1.vectorcraft"):
        (work / forged).parent.mkdir(exist_ok=True)
        (work / forged).write_text('["falso"]', encoding="utf-8")
    (work / master).unlink()

    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"
    # The plan is a harness input too: the sandbox reads it from /ops, never from /job.
    command = sandbox.calls[0]
    assert command[command.index("--commands") + 1] == "/ops/op1.steps.json"
    assert json.loads((inputs / "op1.steps.json").read_text(encoding="utf-8")) == steps()[:1]


def test_resume_with_a_record_only_in_the_old_place_reruns_once(tmp_path: Path) -> None:
    """A project paused in a craft_run before ADR-0044 kept its record in /job/.ops. On resume the steps run
    once more, and that leftover is never read as a record (Review focus 3)."""
    work, inputs, records = harness_folders(tmp_path)
    (work / ".ops").mkdir()
    (work / ".ops/op1.result.json").write_text('[{"id": 1}]', encoding="utf-8")
    (work / ".ops/op1.vectorcraft").write_text("documento vecchio", encoding="utf-8")
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"

    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"


def test_list_files_hides_the_partial_exports(tmp_path: Path) -> None:
    """craft_run's partial exports are the harness's, like the old `.ops`: list_files does not show them."""
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    (tmp_path / ".partial").mkdir()
    (tmp_path / ".partial/op1.vectorcraft").write_text("parziale", encoding="utf-8")
    (tmp_path / "nota.md").write_text("nota", encoding="utf-8")

    listed = json.loads(box.call("l1", "list_files", {})["content"])["files"]

    assert "nota.md" in listed
    assert ".partial/op1.vectorcraft" not in listed


def test_big_images_are_reduced_and_rereads_are_allowed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    Image.new("RGB", (3000, 400)).save(tmp_path / "big.png")
    Image.new("RGB", (400, 400)).save(tmp_path / "ok.png")
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    box = Toolbox(context)
    reduced = box.call("a", "view_image", {"path": "big.png"})
    assert not reduced.get("is_error") and "ridotta" in str(reduced["content"])
    assert not box.call("b", "view_image", {"path": "ok.png"}).get("is_error")
    assert not box.call("c", "view_image", {"path": "ok.png"}).get("is_error")
    again = box.call("d", "view_image", {"path": "ok.png"})
    assert not again.get("is_error") and "già guardata" in str(again["content"])


def test_child_ticket_outside_org_is_refused(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.ledger_path)
    context = ToolContext(
        "design-director",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    arguments = {
        "title": "Ricerca",
        "request": "r",
        "type": "ricerca",
        "assignee": "researcher",
        "outputs": ["a.md"],
        "checks": {},
    }
    assert "non può aprire" in Toolbox(context).call("a", "open_ticket", arguments)["content"]


def test_sandbox_has_no_network_key_or_outside_files(tmp_path: Path) -> None:
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-non-deve-entrare"
    outside = tmp_path / "riservato.txt"
    outside.write_text("x")
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    # What the sandbox sees, not a failed probe: an offline host also fails to connect, and a non-root user
    # cannot write to /usr anyway. Only `lo` exists without the host's network, and /usr is mounted read-only.
    probe = (
        "import os,socket;print(os.environ.get('ANTHROPIC_API_KEY'));"
        f"print(os.path.exists({str(outside)!r}));"
        "print(','.join(name for _, name in socket.if_nameindex()));"
        "print(bool(os.statvfs('/usr').f_flag & os.ST_RDONLY))"
    )
    done = box.run(["python3", "-c", probe])
    del os.environ["ANTHROPIC_API_KEY"]
    assert done.stdout.split() == ["None", "False", "lo", "True"]


def test_sandbox_runs_in_a_new_session(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    # With --new-session bwrap calls setsid() before it unshares the pid namespace, so the session leader is
    # the sandbox's own init (pid 1) and the sid is visible inside. Without it the session is the operator's
    # terminal one, outside the namespace, and getsid(0) reads 0: that is what lets TIOCSTI inject keystrokes.
    probe = "import os;print(os.getsid(0))"
    assert Sandbox(work).run(["python3", "-c", probe]).stdout.split() == ["1"]


def test_sandbox_writes_only_in_its_folder(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    assert box.run(["sh", "-c", f"echo a > {JOB}/ok.txt"]).code == 0
    assert (work / "ok.txt").exists()
    outside = tmp_path / "fuori.txt"
    box.run(["sh", "-c", f"echo a > {outside}; echo a > /etc/agency-probe"])
    assert not outside.exists()
    assert not Path("/etc/agency-probe").exists()


def test_sandbox_tmp_is_size_limited(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    # The totals come first: a 3G fallocate also fails on the file-size limit alone, so it cannot prove the
    # tmpfs bound, and at an unbounded /tmp it would allocate 3 GiB of RAM.
    probe = (
        "import os;"
        "total=lambda path:(lambda s:s.f_blocks*s.f_frsize)(os.statvfs(path));"
        "print(total('/tmp'), total('/home'))"
    )
    assert box.run(["python3", "-c", probe]).stdout.split() == [str(2 * 2**30), str(256 * 2**20)]
    assert box.run(["fallocate", "-l", "3G", "/tmp/x"]).code != 0


def test_sandbox_file_size_is_limited(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    assert Sandbox(work).run(["truncate", "-s", "3G", f"{JOB}/x"]).code != 0
    assert not (work / "x").exists() or (work / "x").stat().st_size < 3 * 2**30


def host_cgroup(path: str) -> Path:
    return Path("/sys/fs/cgroup") / path.removeprefix("0::/").strip()


def test_sandbox_runs_in_its_own_capped_scope(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    # The sandbox has no /sys, so the caps are read from the host while the command is still running: it
    # writes its cgroup into /job and waits for a marker. Every wait is bounded, so a failure cannot hang.
    command = (
        f"cat /proc/self/cgroup > {JOB}/cgroup; i=0; "
        f"while [ ! -e {JOB}/done ] && [ $i -lt 300 ]; do sleep 0.1; i=$((i+1)); done"
    )
    results: list[Completed] = []

    def job() -> None:
        results.append(Sandbox(work).run(["sh", "-c", command], timeout=60))

    runner = threading.Thread(target=job)
    runner.start()
    try:
        deadline = time.monotonic() + 30
        while not ((work / "cgroup").exists() and (work / "cgroup").read_text("utf-8")):
            assert time.monotonic() < deadline, "the sandboxed command never reported its cgroup"
            time.sleep(0.1)
        inside = (work / "cgroup").read_text("utf-8").strip()
        scope = host_cgroup(inside)
        assert inside != Path("/proc/self/cgroup").read_text("utf-8").strip()
        assert (scope / "memory.max").read_text("utf-8").strip() == str(MEMORY_MAX_BYTES)
        assert (scope / "memory.swap.max").read_text("utf-8").strip() == "0"
        assert (scope / "pids.max").read_text("utf-8").strip() == str(TASKS_MAX)
    finally:
        (work / "done").write_text("")
        runner.join(timeout=60)
    assert results
    assert results[0].code == 0


def break_the_user_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`systemd-run --user` cannot reach the user's systemd: the case of a cron job or a bare container."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "no-runtime-dir"))
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)


def test_sandbox_refuses_to_run_without_a_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "work"
    work.mkdir()
    break_the_user_bus(monkeypatch, tmp_path)
    with pytest.raises(SandboxUnavailable) as refused:
        Sandbox(work).run(["sh", "-c", f"echo ran > {JOB}/ran"])
    assert "systemd-run" in str(refused.value)  # the reason names what failed
    assert not (work / "ran").exists()  # the command never started, outside any cap


def test_a_missing_scope_reaches_the_model_as_a_tool_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    break_the_user_bus(monkeypatch, tmp_path)
    result = box.call("c1", "compute", {"code": "print(1)"})
    assert result["is_error"] is True
    assert "scope" in result["content"]
    assert "Traceback" not in result["content"]
    assert "non è riuscito" not in result["content"]  # a refusal (ADR-0046), not a tool crash


def test_master_problem_reads_only_the_header(tmp_path: Path) -> None:
    with (tmp_path / "x.blend").open("wb") as handle:
        handle.write(b"BLENDER")
        handle.truncate(64 * 2**20)  # sparse: no disk, and a full read would show as 64 MiB of memory
    tracemalloc.start()
    try:
        why = master.problem(Sandbox(tmp_path), "x.blend")
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert why is None
    assert peak < 2**20


def test_view_image_refuses_a_huge_file(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "PNG")
    # A valid image, which view_image would otherwise show: zeros alone would be refused as unreadable. Its
    # sparse tail makes it twice the limit, so the peak shows that the read stops near the limit.
    with (tmp_path / "big.png").open("wb") as handle:
        handle.write(buffer.getvalue())
        handle.truncate(2 * 64 * 2**20)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        Ledger(tmp_path / "ledger.db"),
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    tracemalloc.start()
    try:
        result = Toolbox(context).call("a", "view_image", {"path": "big.png"})
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result.get("is_error")
    assert "64 MiB" in result["content"]
    assert peak < 96 * 2**20


@needs_craft
def test_full_project_reaches_the_client_gate_and_is_approved(tmp_path: Path) -> None:
    config = settings(tmp_path)
    brief = tmp_path / "brief.txt"
    brief.write_text("Un segno per un forno di quartiere")
    master, svg = "source/segno.vectorcraft", "exports/segno.svg"
    production = {
        "title": "Segno",
        "request": "Il segno del forno",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": [master, svg, "construction.md"],
        "checks": {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity"]},
        "media": ["vettoriale"],
        "exempt": {"construction.md": "documento di costruzione del segno"},
    }
    qa = {
        "title": "QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [svg],
        "checks": {"*.svg": ["svg_audit"]},
    }
    review = {
        "title": "Critica",
        "request": "Giudica",
        "type": "revisione",
        "assignee": "critic",
        "outputs": [svg],
        "checks": {"*.svg": ["critique"]},
    }
    proof = "proofs/render/exports_segno.svg.png"
    why = (
        "Rispetto alla versione precedente il segno ha un'apertura più netta e regge meglio a piccola scala."
    )
    script = [
        turn(use("open_ticket", "d1", **production)),
        turn(use("hand_off", "d2", note="attendo il segno")),
        turn(use("craft_run", "p1", document=master, steps=steps())),
        turn(use("export_master", "p2", master=master, output=svg)),
        turn(use("compute", "p3", code="print(1)")),
        turn(use("write_file", "p4", path="construction.md", content="unità u")),
        turn(use("write_file", "p5", path="source/precedente.md", content="v0")),
        turn(
            use("run_check", "p6", check="master_open", file=master),
            use("run_check", "p7", check="svg_audit", file=svg),
            use("run_check", "p8", check="svg_parity", file=svg),
        ),
        turn(use("deliver", "p9", note="segno pronto", verdict=None)),
        turn(use("open_ticket", "d3", **qa), use("open_ticket", "d4", **review)),
        turn(use("hand_off", "d5", note="attendo le revisioni")),
        turn(use("run_check", "q1", check="svg_audit", file=svg)),
        turn(use("deliver", "q2", note="tutto regolare", verdict="READY")),
        turn(use("render", "c1", path=svg)),
        turn(use("view_image", "c2", path=proof)),
        turn(
            use(
                "judge",
                "c3",
                file=svg,
                compare=["source/precedente.md"],
                why=why,
                result="PASS",
            )
        ),
        turn(use("deliver", "c4", note="regge", verdict="READY")),
        turn(
            use("accept_ticket", "d6", ticket="T-0002"),
            use("accept_ticket", "d7", ticket="T-0003"),
            use("accept_ticket", "d8", ticket="T-0004"),
        ),
        turn(use("deliver", "d9", note="consegnato", verdict=None)),
    ]
    transport = ScriptedTransport(script)
    session = open_session(config, transport)
    outputs = [master, svg, "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    session.start("forno", brief, outputs, checks, budget=1000.0, explore=False)
    assert session.pending("forno")[0].gate == "final"
    assert session.ledger.status("T-0001")[0] is Status.DELIVERED
    assert session.ledger.status("T-0003") == (Status.ACCEPTED, Verdict.READY)
    session.decide("forno", True, "va bene così")
    assert session.ledger.status("T-0001")[0] is Status.ACCEPTED
    assert session.pending("forno") == []
    assert session.ledger.verify_chain()
    critique = next(r for r in session.ledger.evidence("forno") if r.check_name == "critique")
    assert critique.signer == "critic"
    assert session.ledger.spent("forno") > 0


@needs_craft
def test_client_approval_of_a_root_without_critique_goes_back_to_rework(tmp_path: Path) -> None:
    """The client gate is the last system check: approving a root nobody critiqued sends it back (TST-002)."""
    config = settings(tmp_path)
    brief = tmp_path / "brief.txt"
    brief.write_text("Un segno per un forno di quartiere")
    master, svg = "source/segno.vectorcraft", "exports/segno.svg"
    production = {
        "title": "Segno",
        "request": "Il segno del forno",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": [master, svg, "construction.md"],
        "checks": {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity"]},
        "media": ["vettoriale"],
        "exempt": {"construction.md": "documento di costruzione del segno"},
    }
    qa = {
        "title": "QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [svg],
        "checks": {"*.svg": ["svg_audit"]},
    }
    script = [
        turn(use("open_ticket", "d1", **production)),
        turn(use("hand_off", "d2", note="attendo il segno")),
        turn(use("craft_run", "p1", document=master, steps=steps())),
        turn(use("export_master", "p2", master=master, output=svg)),
        turn(use("write_file", "p3", path="construction.md", content="unità u")),
        turn(
            use("run_check", "p4", check="master_open", file=master),
            use("run_check", "p5", check="svg_audit", file=svg),
            use("run_check", "p6", check="svg_parity", file=svg),
        ),
        turn(use("deliver", "p7", note="segno pronto", verdict=None)),
        turn(use("open_ticket", "d3", **qa)),
        turn(use("hand_off", "d4", note="attendo il QA")),
        turn(use("run_check", "q1", check="svg_audit", file=svg)),
        turn(use("deliver", "q2", note="tutto regolare", verdict="READY")),
        turn(use("accept_ticket", "d5", ticket="T-0002"), use("accept_ticket", "d6", ticket="T-0003")),
        turn(use("deliver", "d7", note="consegnato senza critica", verdict=None)),
        turn(use("block", "d8", reason="manca la critica del segno")),
    ]
    session = open_session(config, ScriptedTransport(script))
    outputs = [master, svg, "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    session.start("forno", brief, outputs, checks, budget=1000.0, explore=False)
    assert session.pending("forno")[0].gate == "final"
    session.decide("forno", True, "va bene così")
    rework = [event for event in session.ledger.history("T-0001") if event.action == "rework"]
    assert len(rework) == 1
    assert rework[0].actor == "router"
    assert rework[0].note.startswith("Accettazione rifiutata dal sistema:")
    assert f"{svg}: manca la prova 'critique'" in rework[0].note
    assert session.ledger.status("T-0001")[0] is not Status.ACCEPTED


class Killed(Exception):
    """The process dies here: nothing after this point reaches the disk."""


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


def test_reviewer_delivers_without_owning_a_master(tmp_path: Path) -> None:
    config = settings(tmp_path)
    work = config.projects_dir / "p/work"
    work.mkdir(parents=True)
    (work / "reviews").mkdir()
    (work / "reviews/critica.md").write_text("referto")
    spec = TicketSpec(
        title="Critica",
        request="Giudica",
        type=TicketType.REVIEW,
        sender="design-director",
        assignee="critic",
        outputs=["reviews/critica.md"],
        checks={"*.svg": ["critique"]},
        media=[Medium.VECTOR],
    )
    run, _, ledger = runner(config, [turn(use("deliver", "t1", note="regge", verdict="REVISE"))])
    ticket = ledger.open(spec, "p")
    assert run.run(ticket).state == "delivered"


def test_observe_accepts_an_image_really_viewed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    Image.new("RGB", (100, 100), (20, 90, 200)).save(tmp_path / "tavola.png")
    ledger = Ledger(config.ledger_path)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    box = Toolbox(context)
    arguments = {
        "file": "tavola.png",
        "seen": "Tavola azzurra piena, bordi netti, nessun elemento o difetto.",
    }
    assert box.call("a", "observe", arguments)["is_error"]
    box.call("b", "view_image", {"path": "tavola.png"})
    assert not box.call("c", "observe", arguments).get("is_error")


def test_redelivery_with_identical_outputs_is_refused(tmp_path: Path) -> None:
    from agency.contracts.ticket import Action

    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "nota.md").write_text("v1")
    ledger = Ledger(config.ledger_path)
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
    ticket = ledger.open(spec, "p")
    context = ToolContext(
        "copywriter",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )
    box = Toolbox(context)
    box.call(
        "a", "record_requirement", {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    )
    assert not box.call("b", "deliver", {"note": "prima", "verdict": None}).get("is_error")
    ledger.apply(ticket, Action.REWORK, "design-director", "cambia il titolo")
    context.finished = None
    assert "identici" in box.call("c", "deliver", {"note": "uguale", "verdict": None})["content"]
    (work / "nota.md").write_text("v2")
    box.call(
        "d", "record_requirement", {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    )
    assert not box.call("e", "deliver", {"note": "corretta", "verdict": None}).get("is_error")


def closing_box(
    tmp_path: Path, spec: TicketSpec, actor: str, *tools: str
) -> tuple[Toolbox, ToolContext, str]:
    """A ticket of `spec` open for `actor`, its work folder ready: the toolbox, its context, the ticket."""
    config = settings(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    ledger = Ledger(config.ledger_path)
    ticket = ledger.open(spec, "p")
    context = ToolContext(
        actor, "p", ticket, "i", ledger, Sandbox(work), CommandIndex([]), FileStore(tmp_path / "artifacts")
    )
    return Toolbox(context, [TOOLS[name] for name in tools]), context, ticket


def crash_after_the_transition(
    box: Toolbox, context: ToolContext, monkeypatch: pytest.MonkeyPatch, name: str, arguments: dict
) -> None:
    """The process dies once the ledger transition has committed, before the resume record is written."""

    def die(*_: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(context.ledger, "record_operation", die)
        with pytest.raises(KeyboardInterrupt):
            box.call("t1", name, arguments)
    assert context.ledger.operation("i:t1") is None
    context.finished = None  # the process restarts: nothing of the old context survives


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
    box, context, ticket = closing_box(tmp_path, spec, "direction-a", "record_requirement", "submit_concept")
    Image.new("RGB", (64, 64), (255, 255, 255)).save(tmp_path / "work" / "schizzo-a.png")
    box.call(
        "a",
        "record_requirement",
        {"file": "schizzo-a.png", "check": "req:letta", "result": "PASS", "note": "ok"},
    )
    context.ledger.add_concept(ConceptRow(project="p", round=1, letter="a", lever="l", idea_ticket=ticket))
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


def test_cli_lists_new_commands() -> None:
    done = subprocess.run(["uv", "run", "agency", "--help"], capture_output=True, text=True, check=True)
    for command in ("run", "resume", "decide", "report"):
        assert command in done.stdout
