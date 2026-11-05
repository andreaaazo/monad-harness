"""Il percorso completo con risposte registrate e Craft veri: nessuna chiamata all'API."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agency.agents.loop import AgentRunner
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import Medium, Status, TicketSpec, TicketType, Verdict
from agency.gateway import BudgetExceeded, ModelGateway, ScriptedTransport
from agency.ledger import Ledger
from agency.runtime import open_session
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import JOB, Sandbox
from agency.tools.surface import Toolbox, ToolContext

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
    entries = Transcript(config.layout.transcript("p", f"{ticket}-a1")).entries()
    answers = [entry for entry in entries if entry.get("message", {}).get("role") == "assistant"]
    assert [entry.get("request_id") for entry in answers] == ["req_blocco"]


def test_agent_ending_without_delivery_is_reminded_then_blocked(tmp_path: Path) -> None:
    config = settings(tmp_path)
    text = {"type": "text", "text": "fatto"}
    run, transport, ledger = runner(config, [turn(text, stop="end_turn"), turn(text, stop="end_turn")])
    ticket = ledger.open(production_spec(), "p")
    assert run.run(ticket).state == "blocked"
    assert len(transport.requests) == 2


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
    probe = (
        "import os,socket;print(os.environ.get('ANTHROPIC_API_KEY'));"
        f"print(os.path.exists({str(outside)!r}));"
        "\ntry:\n socket.create_connection(('1.1.1.1',53),2);print('rete')\nexcept OSError:print('no-rete')"
    )
    done = box.run(["python3", "-c", probe])
    del os.environ["ANTHROPIC_API_KEY"]
    assert done.stdout.split() == ["None", "False", "no-rete"]
    assert box.run(["sh", "-c", "touch /usr/x"]).code != 0


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
    proof = "proofs/render/exports_segno.png"
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


def test_cli_lists_new_commands() -> None:
    done = subprocess.run(["uv", "run", "agency", "--help"], capture_output=True, text=True, check=True)
    for command in ("run", "resume", "decide", "report"):
        assert command in done.stdout
