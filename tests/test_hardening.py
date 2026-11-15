"""Defects found by rereading the system before M2: each one has its test here."""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from PIL import Image
from pydantic import ValidationError

from agency import cli
from agency.agents.loop import AgentRunner
from agency.agents.toolbox import TOOLS, Toolbox, role_tools
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.concept import ConceptCard
from agency.contracts.gate import ConceptGate, Gate
from agency.contracts.layout import RelativeDataRoot
from agency.contracts.project import ProjectName, parse_project_name
from agency.contracts.run import Fingerprint
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.evaluation.blind import CannotCompare
from agency.gateway import ModelGateway
from agency.insights.domain import Provenance
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from agency.ledger.models import ArtifactRow, ConceptRow, EvidenceRow, JudgmentRow, RunRow, UsageRow
from agency.qa import checks as qa
from agency.qa import delivery, evidence
from agency.telemetry import report
from agency.toolkit.base import ToolContext
from agency.toolkit.review import _seen_proof
from agency.workshop import craft
from agency.workshop.craft import Command, CommandIndex
from agency.workshop.files import OutsidePerimeter, is_file_under
from agency.workshop.sandbox import Completed, Sandbox
from support.concepts import open_idea
from support.scripted import ScriptedTransport
from support.settings import settings


@pytest.fixture(autouse=True)
def own_data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI command locks its project under the data folder first: keep that out of `.data`."""
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture(autouse=True)
def sandbox_scope_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run`, `resume` and `decide` probe the sandbox scope first: no test of this file spawns systemd-run."""
    monkeypatch.setattr(cli, "scope_problem", lambda: None)


def context(tmp_path: Path, actor: str = "identity-designer", ticket: str = "T-1") -> ToolContext:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    inputs = settings(tmp_path).layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True, exist_ok=True)
    return ToolContext(
        actor,
        "p",
        ticket,
        "i",
        Ledger(tmp_path / "l.sqlite"),
        Sandbox(work, ops=inputs),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )


OPERATIONS = itertools.count(1)


needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def call(ctx: ToolContext, tool_name: str, **arguments: object) -> dict:
    """Each call has its own id: with the same id, the system repeats the first outcome, as it should."""
    return Toolbox(ctx, role_tools(ctx.actor)).call(f"t{next(OPERATIONS)}", tool_name, arguments)


def spec(**extra: Any) -> TicketSpec:
    values: dict[str, Any] = {
        "title": "Segno",
        "request": "Disegna",
        "type": TicketType.PRODUCTION,
        "sender": "design-director",
        "assignee": "identity-designer",
        "outputs": ["a.md"],
        "checks": {"*.md": ["req:testo"]},
        "media": [Medium.NONE],
        "medium_why": "solo testo, nessun mezzo visivo",
    }
    return TicketSpec.model_validate(values | extra)


# Perimeter


@pytest.mark.parametrize("name", ["../..", "../../.", "logo-design/../../.."])
def test_read_skill_cannot_leave_the_skills(tmp_path: Path, name: str) -> None:
    """The API key is in the repository root: `name` must not reach it."""
    result = call(context(tmp_path), "read_skill", name=name, file="pyproject.toml")
    assert result.get("is_error")
    assert "[project]" not in str(result["content"])


def test_read_skill_still_reads_skills_and_org(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    assert not call(ctx, "read_skill", name="logo-design").get("is_error")
    assert not call(ctx, "read_skill", name="org", file="craft.md").get("is_error")


def test_list_files_cannot_look_at_another_direction(tmp_path: Path) -> None:
    other = tmp_path / "altra-direzione"
    other.mkdir()
    (other / "segreto.txt").write_text("idea altrui")
    result = call(context(tmp_path), "list_files", pattern="../altra-direzione/*")
    assert "segreto" not in str(result["content"])


def test_list_files_ignores_links_that_leave_the_work(tmp_path: Path) -> None:
    (tmp_path / "fuori.txt").write_text("fuori")
    ctx = context(tmp_path)
    (ctx.work / "dentro.txt").write_text("dentro")
    (ctx.work / "link.txt").symlink_to(tmp_path / "fuori.txt")
    result = str(call(ctx, "list_files")["content"])
    assert "dentro.txt" in result
    assert "link.txt" not in result


@pytest.mark.sandbox
def test_compute_never_writes_through_a_planted_ops_symlink(tmp_path: Path) -> None:
    """Sandboxed code plants `.ops` as a link to a host folder. The next compute writes nothing there.

    Since ADR-0044 the script goes to /ops, outside the work folder: compute never opens `/job/.ops`.
    The host folder here is a scratch one. In the audit's reproduction it was Alembic's migrations folder.
    """
    ctx = context(tmp_path)
    host = tmp_path / "host-folder"
    host.mkdir()
    plant = f"import os\nos.symlink({str(host)!r}, '/job/.ops')\n"
    assert json.loads(call(ctx, "compute", code=plant)["content"])["exit"] == 0
    assert (ctx.work / ".ops").is_symlink()
    payload = "print('scritto dal modello')\n"

    result = call(ctx, "compute", code=payload)

    assert json.loads(result["content"]) == {"exit": 0, "output": "scritto dal modello\n"}
    assert list(host.iterdir()) == []


class IdleSandbox(Sandbox):
    """Runs nothing: what matters is what the harness writes before the sandbox starts."""

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        return Completed(1, "", "")


def test_craft_run_never_writes_through_a_planted_ops_symlink(tmp_path: Path) -> None:
    """The same link, left by an earlier compute: craft_run must not write its plan into the host folder.

    Since ADR-0044 the plan goes to /ops and craft_run never opens `/job/.ops`: the run goes ahead, and fails
    only because this sandbox runs nothing.
    """
    work, host = tmp_path / "work", tmp_path / "host-folder"
    work.mkdir()
    host.mkdir()
    (work / ".ops").symlink_to(host, target_is_directory=True)
    layout = settings(tmp_path).layout
    inputs = layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    sandbox, records = IdleSandbox(work, ops=inputs), layout.ops_records(ProjectName("p"), "i")
    steps = [{"command": "path.create"}]

    result = craft.run_steps(sandbox, index, "segno.vectorcraft", steps, "op1", records)

    assert result == {"ok": False, "error": ""}
    assert list(host.iterdir()) == []


def test_a_reviewer_cannot_leave_reviews_with_dotdot(tmp_path: Path) -> None:
    ctx = context(tmp_path, actor="critic")
    brief = ctx.work / "brief.md"
    brief.write_text("il brief del cliente", encoding="utf-8")
    assert call(ctx, "write_file", path="brief.md", content="riscritto")["is_error"]

    result = call(ctx, "write_file", path="reviews/../brief.md", content="riscritto da un revisore")

    # Since Task 2.2 the no-follow helper refuses `..` first, with the perimeter's message.
    assert result.get("is_error")
    assert "fuori dalla cartella del lavoro" in str(result["content"])
    assert brief.read_text(encoding="utf-8") == "il brief del cliente"


def reviewer_with_brief(tmp_path: Path) -> tuple[ToolContext, Path]:
    ctx = context(tmp_path, actor="critic")
    brief = ctx.work / "brief.md"
    brief.write_text("il brief del cliente", encoding="utf-8")
    return ctx, brief


def tree(folder: Path) -> list[str]:
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


@pytest.mark.parametrize(
    "path",
    [
        "reviews/./../brief.md",
        "reviews//../brief.md",
        "/reviews/../brief.md",
        "Reviews/brief.md",
        r"reviews\..\brief.md",
    ],
)
def test_a_reviewer_cannot_leave_reviews_by_another_spelling(tmp_path: Path, path: str) -> None:
    """SEC-004 (Task 2.7) was not reproduced: the routes its probe tried stay refused, and write nothing."""
    ctx, brief = reviewer_with_brief(tmp_path)
    before = tree(ctx.work)
    assert call(ctx, "write_file", path=path, content="riscritto da un revisore").get("is_error")
    assert brief.read_text(encoding="utf-8") == "il brief del cliente"
    assert tree(ctx.work) == before


@pytest.mark.parametrize(
    ("link", "target", "path"),
    [("reviews", ".", "reviews/brief.md"), ("reviews/up", "..", "reviews/up/brief.md")],
)
def test_a_reviewer_cannot_leave_reviews_through_a_link(
    tmp_path: Path, link: str, target: str, path: str
) -> None:
    """A link the sandbox planted in or as `reviews/` is never followed (SEC-004, Task 2.7)."""
    ctx, brief = reviewer_with_brief(tmp_path)
    (ctx.work / link).parent.mkdir(parents=True, exist_ok=True)
    (ctx.work / link).symlink_to(target)
    assert call(ctx, "write_file", path=path, content="riscritto da un revisore").get("is_error")
    assert brief.read_text(encoding="utf-8") == "il brief del cliente"


def test_a_review_written_over_a_planted_link_replaces_the_link_not_its_target(tmp_path: Path) -> None:
    ctx, brief = reviewer_with_brief(tmp_path)
    review = ctx.work / "reviews" / "x.md"
    review.parent.mkdir()
    review.symlink_to("../brief.md")
    assert not call(ctx, "write_file", path="reviews/x.md", content="il referto").get("is_error")
    assert not review.is_symlink() and review.read_text(encoding="utf-8") == "il referto"
    assert brief.read_text(encoding="utf-8") == "il brief del cliente"


# Ticket paths


def with_path(field: str, path: str) -> TicketSpec:
    """A review-free production spec whose `field` carries `path`."""
    if field == "outputs":
        return spec(outputs=[path], checks={"*": ["req:testo"]})
    if field == "inputs":
        return spec(inputs=[path])
    return spec(checks={path: ["req:testo"]})


@pytest.mark.parametrize("field", ["outputs", "inputs", "checks"])
@pytest.mark.parametrize("path", ["/etc/passwd", "/**", "../x.png", "exports/../../x.png"])
def test_ticket_paths_must_stay_inside_the_work_folder(field: str, path: str) -> None:
    with pytest.raises(ValidationError, match=f"{re.escape(path)} è fuori dalla cartella del lavoro"):
        with_path(field, path)


@pytest.mark.parametrize("field", ["outputs", "inputs", "checks"])
@pytest.mark.parametrize(
    "path", ["exports/segno.svg", "reviews/*.md", "**/*.png", "segno..svg", "v1..2/a.png"]
)
def test_ticket_paths_inside_the_work_folder_are_accepted(field: str, path: str) -> None:
    assert with_path(field, path)


def test_open_ticket_refuses_an_absolute_review_output_without_globbing_it(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    host = tmp_path / "host.png"
    host.write_text("fuori", encoding="utf-8")
    for output in (str(host), str(tmp_path / "nope.png")):
        result = call(
            ctx,
            "open_ticket",
            title="Giudizio",
            request="Guarda",
            type="revisione",
            assignee="critic",
            outputs=[output],
            checks={"*.png": ["req:testo"]},
        )
        assert result.get("is_error")
        # The same refusal whether the file exists or not: no oracle.
        assert f"{output} è fuori dalla cartella del lavoro" in str(result["content"])
    assert not ctx.ledger.tickets("p")


# Delegations


def test_ticket_to_a_role_not_yet_ported_is_refused(tmp_path: Path) -> None:
    """Without a prompt, the role would bring the work down when its turn came."""
    ctx = context(tmp_path, "design-director")
    result = call(
        ctx,
        "open_ticket",
        title="Lockup",
        request="Compone il nome",
        type="produzione",
        assignee="typographer",
        outputs=["a.md"],
        checks={"*.md": ["req:testo"]},
        media=["nessuno"],
    )
    assert result.get("is_error")
    assert "typographer" in str(result["content"])
    assert not ctx.ledger.tickets("p")


# Resume


def test_transcript_survives_a_torn_last_line(tmp_path: Path) -> None:
    first = Transcript(tmp_path / "t.jsonl")
    first.append({"role": "user", "content": "uno"})
    with first.path.open("a", encoding="utf-8") as handle:
        handle.write('{"message": {"role": "assis')  # a process killed mid-line
    resumed = Transcript(first.path)
    assert [m["content"] for m in resumed.messages()] == ["uno"]
    resumed.append({"role": "user", "content": "due"})
    assert [m["content"] for m in Transcript(first.path).messages()] == ["uno", "due"]


def test_transcript_keeps_a_whole_line_that_only_lost_its_newline(tmp_path: Path) -> None:
    first = Transcript(tmp_path / "t.jsonl")
    with first.path.open("a", encoding="utf-8") as handle:
        handle.write('{"message": {"role": "user", "content": "intera"}}')
    resumed = Transcript(first.path)
    resumed.append({"role": "user", "content": "due"})
    assert [m["content"] for m in Transcript(first.path).messages()] == ["intera", "due"]


def test_a_response_keeps_its_request_id_and_the_resumed_messages_stay_the_same(tmp_path: Path) -> None:
    """The replay view matches each turn to its usage row by request_id; a resume reads only the messages."""
    transcript = Transcript(tmp_path / "t.jsonl")
    transcript.append({"role": "user", "content": "uno"})
    transcript.append({"role": "assistant", "content": [{"type": "text", "text": "due"}]}, request_id="req_7")
    entries = Transcript(transcript.path).entries()
    assert [entry.get("request_id") for entry in entries] == [None, "req_7"]
    assert Transcript(transcript.path).messages() == [
        {"role": "user", "content": "uno"},
        {"role": "assistant", "content": [{"type": "text", "text": "due"}]},
    ]


def test_broken_image_does_not_kill_the_work(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    (ctx.work / "rotta.png").write_bytes(b"non sono un'immagine")
    assert call(ctx, "view_image", path="rotta.png").get("is_error")


def test_unexpected_tool_failure_goes_back_to_the_model(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    (ctx.work / "cartella.md").mkdir()
    result = call(ctx, "write_file", path="cartella.md", content="testo")
    assert result.get("is_error")


# Loop


def runner(config: Settings, responses: list[dict]) -> tuple[AgentRunner, ScriptedTransport, Ledger]:
    """Project `p`, with the cap the client would declare: without one the gateway spends nothing
    (ADR-0043)."""
    ledger = Ledger(config.layout.ledger)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(responses)
    index = CommandIndex([])
    return (
        AgentRunner(
            ModelGateway(transport, ledger, config), ledger, config, index, FileStore(config.layout.artifacts)
        ),
        transport,
        ledger,
    )


def reply(*blocks: dict, stop: str = "tool_use") -> dict:
    return {
        "content": list(blocks),
        "stop_reason": stop,
        "model": "claude-opus-5-5",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def text(words: str) -> dict:
    return {"type": "text", "text": words}


def tool(name: str, tool_id: str, **arguments: object) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def test_reminder_names_only_the_tools_of_the_phase(tmp_path: Path) -> None:
    run, transport, ledger = runner(
        settings(tmp_path),
        [reply(text("Ho finito"), stop="end_turn"), reply(tool("block", "b1", reason="manca tutto"))],
    )
    root = ledger.open(spec(type=TicketType.DELIVERY, assignee="design-director", sender="router"), "p")
    run.run(root, 1, mode="select")
    reminder = transport.requests[1]["messages"][-1]["content"]
    assert "select_concepts" in reminder
    assert "deliver" not in reminder
    assert "hand_off" not in reminder


def test_agent_working_again_after_a_reminder_can_be_reminded_again(tmp_path: Path) -> None:
    """The reminder is not a strike: an agent that went back to work is not blocked at the next pause."""
    done = reply(text("Fatto"), stop="end_turn")
    work = reply(tool("list_files", "l1"))
    run, _, ledger = runner(
        settings(tmp_path), [done, work, done, reply(tool("block", "b1", reason="ora mi fermo"))]
    )
    ticket = ledger.open(spec(), "p")
    outcome = run.run(ticket)
    assert outcome.note == "ora mi fermo"


def test_nothing_runs_after_the_tool_that_closes_the_ticket(tmp_path: Path) -> None:
    """Writing after the delivery would make the work differ from what was delivered."""
    run, _, ledger = runner(
        settings(tmp_path),
        [
            reply(
                tool("block", "b1", reason="manca il brief"),
                tool("write_file", "w1", path="tardi.md", content="dopo la fine"),
            )
        ],
    )
    ticket = ledger.open(spec(), "p")
    run.run(ticket)
    assert ledger.status(ticket)[0] is Status.BLOCKED
    assert not (settings(tmp_path).project_dir(ProjectName("p")) / "work/tardi.md").exists()


def test_the_runner_refuses_a_stored_name_the_rule_rejects_before_it_writes(tmp_path: Path) -> None:
    """A name read back from the registry becomes a folder only after the rule has seen it (COR-013)."""
    config = settings(tmp_path)
    run, transport, ledger = runner(config, [])
    ledger.set_project("Merlo", 25.0)
    ticket = ledger.open(spec(), "Merlo")
    with pytest.raises(ValueError, match="nome di progetto non valido: 'Merlo'"):
        run.run(ticket)
    assert transport.requests == []
    assert not config.layout.transcripts.exists()
    assert not config.projects_dir.exists()


def paused() -> dict:
    block = {"type": "server_tool_use", "id": "srv1", "name": "web_search", "input": {"query": "merli"}}
    return reply(block, stop="pause_turn")


def test_paused_turn_resends_the_history_as_it_is(tmp_path: Path) -> None:
    """Web searches pause like this: no message is added, and the server resumes on its own."""
    run, transport, ledger = runner(
        settings(tmp_path), [paused(), reply(tool("block", "b1", reason="ricerca finita"))]
    )
    ticket = ledger.open(spec(), "p")
    assert run.run(ticket).state == "blocked"
    sent = transport.requests[1]["messages"]
    assert [message["role"] for message in sent] == ["user", "assistant"]
    assert sent[-1]["content"][-1]["type"] == "server_tool_use"


def test_paused_turn_interrupted_resumes_the_same_way(tmp_path: Path) -> None:
    config = settings(tmp_path)
    run, transport, ledger = runner(config, [reply(tool("block", "b1", reason="ricerca finita"))])
    ticket = ledger.open(spec(), "p")
    transcript = Transcript(config.data_dir / "runs/p" / f"{ticket}-a1.jsonl")
    transcript.append({"role": "user", "content": "lavora"})
    transcript.append({"role": "assistant", "content": paused()["content"]})
    run.run(ticket)
    assert [message["role"] for message in transport.requests[0]["messages"]] == ["user", "assistant"]


def test_answer_interrupted_before_the_reminder_gets_it_on_resume(tmp_path: Path) -> None:
    """A conversation cannot restart from a text answer: the API would reject it."""
    config = settings(tmp_path)
    run, transport, ledger = runner(config, [reply(tool("block", "b1", reason="mi fermo"))])
    ticket = ledger.open(spec(), "p")
    transcript = Transcript(config.data_dir / "runs/p" / f"{ticket}-a1.jsonl")
    transcript.append({"role": "user", "content": "lavora"})
    transcript.append({"role": "assistant", "content": [text("Ho finito")]})
    run.run(ticket)
    sent = transport.requests[0]["messages"]
    assert sent[-1]["role"] == "user"
    assert "Non hai concluso" in sent[-1]["content"]


# Registry


def test_parallel_writers_never_hit_a_locked_database(tmp_path: Path) -> None:
    """Five explorers write at once: reading and then writing must never fail."""
    ledger = Ledger(tmp_path / "l.sqlite")
    tickets = [ledger.open(spec(title=f"Lavoro {i}"), "p") for i in range(6)]
    errors: list[Exception] = []
    start = threading.Barrier(len(tickets))

    def work(ticket: str) -> None:
        try:
            start.wait(timeout=20)
            for step in range(25):
                ledger.record_usage(usage(ticket, step))
                ledger.add_evidence(
                    EvidenceRow(
                        at="2026-11-01T00:00:00+00:00",
                        project="p",
                        file=f"{ticket}-{step}.md",
                        sha256="0" * 64,
                        check_name="req:testo",
                        result="PASS",
                        signer="identity-designer",
                        ticket_id=ticket,
                    )
                )
                ledger.record_operation(f"{ticket}:{step}", "i", "write_file", "{}")
            ledger.apply(ticket, Action.BLOCK, "identity-designer", "fine")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(ticket,)) for ticket in tickets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors[:2]
    assert ledger.verify_chain()


def test_two_processes_share_one_chain_of_hashes(tmp_path: Path) -> None:
    """Two jobs started together are two processes: the in-process lock is not enough."""
    path = tmp_path / "l.sqlite"
    errors: list[Exception] = []
    start = threading.Barrier(4)

    def work(project: str) -> None:
        try:
            start.wait(timeout=20)
            ledger = Ledger(path)  # each instance has its own lock, like another process
            for index in range(15):
                ticket = ledger.open(spec(title=f"Lavoro {index}"), project)
                ledger.apply(ticket, Action.BLOCK, "identity-designer", "fine")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(f"p{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors[:2]
    ledger = Ledger(path)
    assert ledger.verify_chain()
    assert sum(len(ledger.tickets(f"p{n}")) for n in range(4)) == 60


def usage(ticket: str, step: int, at: str = "2026-11-01T00:00:00+00:00", instance: str = "i") -> UsageRow:
    return UsageRow(
        at=at,
        project="p",
        ticket_id=ticket,
        role="identity-designer",
        instance=instance,
        model="claude-opus-5-5",
        input_tokens=step,
        output_tokens=1,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=0,
        cost_usd=0.01,
        stop_reason="tool_use",
        request_id="",
    )


def test_report_counts_how_many_worked_at_once(
    tmp_path: Path, report_of: Callable[[Path, str], ProjectReport]
) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ticket = ledger.open(spec(), "p")
    for name in "abcde":
        ledger.record_usage(usage(ticket, 1, "2026-11-01T10:00:00+00:00", name))
        ledger.record_usage(usage(ticket, 2, "2026-11-01T10:05:00+00:00", name))
    ledger.record_usage(usage(ticket, 3, "2026-11-01T11:00:00+00:00", "dopo"))
    view = report_of(tmp_path / "l.sqlite", "p")
    assert view.parallel == 5
    assert "in parallelo: 5" in report.render(view)


# Proofs


def test_a_crashed_measure_is_not_evidence(tmp_path: Path) -> None:
    (tmp_path / "segno.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"></svg>')
    outcome = qa.execute(Sandbox(tmp_path, settings(tmp_path).toolchain_dir), "optical_check", "segno.svg")
    assert outcome.result == "FAIL"
    assert not outcome.proofs


# Commands: a typo must not cost an exploration


class FakeSession:
    def __init__(self, gates: list[Gate], ledger: Ledger | None = None) -> None:
        self.gates = gates
        self.calls: list[tuple] = []
        self.ledger = ledger or Ledger(Path("/dev/null"))
        self.settings = Settings(_env_file=None)  # type: ignore[call-arg]

    def pending(self, _: str) -> list[Gate]:
        return self.gates

    def decide(self, *arguments: object) -> str:
        self.calls.append(arguments)
        self.gates = []
        return ""


CONCEPT = ConceptGate(ticket="T-0001", files=[], options=["V", "X"], recommended="V", reasons="")


def decide(session: FakeSession, monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
    folder = Path(str(session.ledger.engine.url.database)).parent
    monkeypatch.setenv("AGENCY_DATA_DIR", str(folder))
    Ledger(folder / "ledger.sqlite")  # `decide` needs a registry to exist
    monkeypatch.setattr("agency.process.session.open_session", lambda _, record=False: session)
    monkeypatch.setattr(cli, "_show", lambda *_: 0)
    return cli.main(["decide", "officina", *arguments, "--text", "Scelgo"])


@pytest.mark.parametrize("arguments", [("--approve",), ("--approve", "--choice", "Q")])
def test_decide_refuses_a_choice_that_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: tuple[str, ...]
) -> None:
    session = FakeSession([CONCEPT], Ledger(tmp_path / "l.sqlite"))
    assert decide(session, monkeypatch, *arguments) == 1
    assert not session.calls


def test_decide_accepts_a_lowercase_letter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([CONCEPT], Ledger(tmp_path / "l.sqlite"))
    assert decide(session, monkeypatch, "--approve", "--choice", "v") == 0
    assert session.calls == [("officina", True, "Scelgo", "V")]


def test_decide_without_a_gate_does_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    assert decide(session, monkeypatch, "--approve") == 1
    assert not session.calls


def test_run_refuses_a_project_that_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.set_project("officina", 30)
    session = FakeSession([], ledger)
    monkeypatch.setattr("agency.process.session.open_session", lambda _, record=False: session)
    assert cli.main(["run", "officina", "brief.md", "--budget", "30"]) == 1
    assert "esiste già" in capsys.readouterr().out


def test_run_does_not_start_without_a_declared_budget(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whoever starts the project declares the cap (ADR-0043): a value from the environment is not the
    client's choice."""
    monkeypatch.setenv("AGENCY_PROJECT_BUDGET_USD", "40")
    opened: list[object] = []
    monkeypatch.setattr(
        "agency.process.session.open_session", lambda settings, record=False: opened.append(settings)
    )
    with pytest.raises(SystemExit) as stopped:
        cli.main(["run", "officina", "brief.md"])
    assert stopped.value.code == 2
    assert "--budget" in capsys.readouterr().err
    assert opened == []


@pytest.mark.parametrize("amount", ["0", "-5", "nan", "inf", "trenta"])
@pytest.mark.parametrize("command", [["run", "officina", "brief.md", "--budget"], ["budget", "officina"]])
def test_a_budget_is_a_positive_amount_of_dollars(
    command: list[str], amount: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "agency.process.session.open_session", lambda _, record=False: pytest.fail("should not have started")
    )
    with pytest.raises(SystemExit) as stopped:
        cli.main([*command, amount])
    assert stopped.value.code == 2
    assert "importo positivo in dollari" in capsys.readouterr().err


def test_settings_have_no_budget_of_their_own() -> None:
    """There used to be AGENCY_PROJECT_BUDGET_USD: $25 in the code, $40 in the environment, $30 in the
    roadmap."""
    assert not any("budget" in name for name in Settings.model_fields)


def test_budget_of_an_unknown_project_is_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    Ledger(tmp_path / "ledger.sqlite")  # an existing registry that does not know the project
    assert cli.main(["budget", "fantasma", "40"]) == 1
    assert "fantasma" in capsys.readouterr().out


def cli_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Data and project folders of the test's own, and no .env: the CLI builds its settings from here."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "data" / "ledger.sqlite"


def scripted_run(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> ScriptedTransport:
    """`agency run` with the real session, over scripted responses: no call leaves the machine."""
    from agency.process.session import open_session

    transport = ScriptedTransport(responses)
    monkeypatch.setattr(
        "agency.process.session.open_session",
        lambda settings, record=False: open_session(settings, transport, record=record),
    )
    return transport


BLOCK_AT_ONCE = {
    "content": [{"type": "tool_use", "id": "t1", "name": "block", "input": {"reason": "prova del tetto"}}],
    "stop_reason": "tool_use",
    "model": "claude-sonnet-5-5",
    "usage": {"input_tokens": 100, "output_tokens": 20},
}


@needs_craft
def test_run_hands_budget_and_model_to_the_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The declared cap and the chosen model are what the run starts under (TST-005, ADR-0043)."""
    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno di quartiere", encoding="utf-8")
    transport = scripted_run(monkeypatch, [BLOCK_AT_ONCE])
    command = ["run", "forno", str(brief), "--budget", "12", "--model", "claude-sonnet-5-5"]
    assert cli.main(command) == 0
    row = Ledger(path).project("forno")
    assert row is not None
    assert (row.budget_usd, row.model) == (12.0, "claude-sonnet-5-5")
    assert transport.requests[0]["model"] == "claude-sonnet-5-5"


def test_budget_command_changes_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    assert cli.main(["budget", "forno", "40"]) == 0
    row = Ledger(path).project("forno")
    assert row is not None and row.budget_usd == 40.0
    assert capsys.readouterr().out.startswith("forno: budget portato a 40.00 $")


@needs_craft
def test_a_brief_that_is_not_utf8_leaves_no_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_bytes("Un segno per il caffè".encode("cp1252"))
    scripted_run(monkeypatch, [])
    assert cli.main(["run", "forno", str(brief), "--budget", "5"]) == 1
    out = capsys.readouterr().out
    assert "non è UTF-8" in out
    assert len(out.strip().splitlines()) == 1
    assert Ledger(path).project("forno") is None
    assert Ledger(path).runs("forno") == []


@needs_craft
def test_an_empty_brief_leaves_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agency.process.session import open_session

    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("", encoding="utf-8")
    session = open_session(Settings(), ScriptedTransport([]))
    with pytest.raises(ValidationError) as refused:
        session.start("p", brief, cli.LOGO_OUTPUTS, cli.LOGO_CHECKS, budget=5.0)
    assert "request" in str(refused.value)
    assert Ledger(path).project("p") is None


@needs_craft
def test_a_refused_contract_leaves_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agency.process.session import open_session
    from agency.qa.delivery import ContractRefused

    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno", encoding="utf-8")
    session = open_session(Settings(), ScriptedTransport([]))
    with pytest.raises(ContractRefused):
        session.start("p", brief, ["logo.svg"], {"nulla.png": []}, budget=5.0)
    assert Ledger(path).project("p") is None


def test_project_names(tmp_path: Path) -> None:
    """A project name is a DNS label: it becomes a folder, and later a subdomain (COR-013)."""
    for name in ["merlo", "merlo4", "officina-e2e", "p", "a" * 63, "a-b-c", "0", "9-9"]:
        assert parse_project_name(name) == name
    for bad in ["../x", "a/b", "", "Merlo", "-a", "a-", "merlo\n", "a" * 64, "a.b", "a b", "à", "a_b", ".."]:
        with pytest.raises(ValueError) as refused:
            parse_project_name(bad)
        assert "nome di progetto non valido" in str(refused.value)
        assert repr(bad) in str(refused.value)


@needs_craft
def test_a_project_name_that_would_leave_projects_never_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agency.process.session import open_session

    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno", encoding="utf-8")
    session = open_session(Settings(), ScriptedTransport([]))
    for bad in ["../x", "a/b", ""]:
        with pytest.raises(ValueError, match="nome di progetto non valido"):
            session.start(bad, brief, cli.LOGO_OUTPUTS, cli.LOGO_CHECKS, budget=5.0)
    assert not (tmp_path / "x").exists()  # `projects/../x`
    assert not (tmp_path / "projects").exists()
    assert Ledger(path).project("../x") is None
    assert Ledger(path).project("") is None


def test_every_command_refuses_a_bad_project_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno", encoding="utf-8")
    scripted_run(monkeypatch, [])
    for command in [
        ["run", "../x", str(brief), "--budget", "5"],
        ["resume", "../x"],
        ["decide", "../x", "--approve", "--text", "ok"],
        ["budget", "../x", "40"],
        ["report", "../x"],
        ["runs", "../x"],
        ["artifacts", "../x"],
    ]:
        with pytest.raises(SystemExit) as stopped:
            cli.main(command)
        assert stopped.value.code == 2, command
        err = capsys.readouterr().err
        assert "nome di progetto non valido: '../x'" in err, command
        assert "Traceback" not in err
    assert not path.exists()  # no command opened, let alone created, the registry
    assert not (tmp_path / "x").exists()
    assert not (tmp_path / "data" / "locks").exists()


def test_an_invalid_stored_name_is_reported_not_crashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A registry written before the rule may hold `Merlo`: the report refuses it in one line (COR-013)."""
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("Merlo", 5.0)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["report", "Merlo"])
    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert "nome di progetto non valido: 'Merlo'" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


@needs_craft
def test_resume_without_saved_work_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 5.0, "", "")
    scripted_run(monkeypatch, [])
    assert cli.main(["resume", "forno"]) == 1
    out = capsys.readouterr().out
    assert "nessun lavoro salvato" in out
    assert len(out.strip().splitlines()) == 1
    assert Ledger(path).runs("forno") == []


def test_network_failure_keeps_the_work_and_says_how_to_resume(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def fail() -> None:
        raise anthropic.APIConnectionError(request=request)

    assert cli._guarded("officina", session, fail) == 3  # type: ignore[attr-defined]
    assert "agency resume officina" in capsys.readouterr().out


def test_api_error_text_reaches_the_terminal_without_control_sequences(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The message of an `APIError` carries the response body of the API or of a proxy in between (2.F55)."""
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def fail() -> None:
        raise anthropic.APIError("proxy\x1b]52;c;ZWNobyBwd25lZA==\x07 giù", request, body=None)

    assert cli._guarded("officina", session, fail) == 3  # type: ignore[attr-defined]
    out = capsys.readouterr().out
    assert "API NON DISPONIBILE: proxy]52;c;ZWNobyBwd25lZA== giù" in out
    assert "\x1b" not in out and "\x07" not in out


def test_blocked_outcome_is_shown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    monkeypatch.setattr(cli, "_show", lambda *_: 0)
    cli._guarded("officina", session, lambda: "bloccato: manca il brief")  # type: ignore[attr-defined]
    assert "manca il brief" in capsys.readouterr().out


# Review contracts: on merlo3, four reviewers finished their work without being able to deliver it


SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'


def studio(tmp_path: Path) -> ToolContext:
    director = context(tmp_path, "design-director", "T-0")
    (director.work / "exports").mkdir(exist_ok=True)
    (director.work / "exports/segno.svg").write_text(SVG)
    director.ticket_id = director.ledger.open(spec(type=TicketType.DELIVERY, assignee="design-director"), "p")
    return director


def open_review(director: ToolContext, assignee: str = "critic", **extra: Any) -> dict:
    kind = "revisione" if assignee == "critic" else "qa"
    values: dict[str, Any] = {"title": "Revisione", "request": "Giudica", "type": kind} | extra
    return call(director, "open_ticket", assignee=assignee, media=["vettoriale"], **values)


def signed_by(director: ToolContext, role: str, ticket: str) -> ToolContext:
    return ToolContext(
        role,
        "p",
        ticket,
        f"{ticket}-i",
        director.ledger,
        director.sandbox,
        CommandIndex([]),
        director.artifacts,
    )


def proof(reviewer: ToolContext, check: str, result: str = "PASS") -> None:
    file = "exports/segno.svg"
    evidence.record(
        reviewer.ledger, reviewer.work, "p", file, check, result, reviewer.actor, reviewer.ticket_id, "x.png"
    )


@pytest.mark.parametrize(
    ("outputs", "checks"),
    [
        (["review/critica.md"], {"review/critica.md": ["critique"]}),  # T-0030
        (["qa/referto.md"], {"qa/referto.md": ["req:colore"]}),  # T-0031
        (["reviews/referto.md"], {"*.md": ["visual_review"]}),  # T-0032
        (["reviews/critica.md"], {"*.md": ["critique"]}),  # T-0033
        (["reviews/critica.md"], {"reviews/critica.md": ["req:colore"]}),
        (["exports/segno.svg", "exports/nuovo.svg"], {"*.svg": ["critique"]}),
    ],
)
def test_a_review_nobody_could_deliver_is_refused_at_opening(
    tmp_path: Path, outputs: list[str], checks: dict[str, list[str]]
) -> None:
    result = open_review(studio(tmp_path), outputs=outputs, checks=checks)
    assert result.get("is_error"), result


def test_a_review_can_be_opened_before_the_file_it_judges_exists(tmp_path: Path) -> None:
    director = studio(tmp_path)
    production = spec(
        outputs=["exports/nuovo.svg"], checks={"*.svg": ["svg_audit"]}, parent=director.ticket_id
    )
    director.ledger.open(production, "p")
    opened = open_review(
        director,
        outputs=["exports/nuovo.svg", "reviews/critica.md"],
        checks={"*.svg": ["critique"]},
    )
    assert not opened.get("is_error"), opened


def test_the_refusal_shows_the_director_the_contract_to_write(tmp_path: Path) -> None:
    """The director's first attempt, on merlo3: the message led the director astray."""
    result = open_review(studio(tmp_path), outputs=["reviews/critica.md"], checks={"*.svg": ["critique"]})
    assert result.get("is_error")
    assert "exports/segno.svg" in result["content"]
    assert "reviews/critica.md" in result["content"]


@pytest.mark.parametrize("check", ["visual_review", "critique"])
def test_a_visual_check_needs_something_that_can_be_rendered(check: str) -> None:
    """An observation and a judgement are both made by looking at a render of the file."""
    with pytest.raises(delivery.ContractRefused, match="render"):
        delivery.validate(spec(checks={"*.md": [check]}))


def test_a_review_delivers_and_is_accepted_with_the_contract_the_refusal_suggests(tmp_path: Path) -> None:
    director = studio(tmp_path)
    opened = open_review(
        director,
        outputs=["exports/segno.svg", "reviews/critica.md"],
        checks={"*.svg": ["critique"]},
    )
    ticket = json.loads(opened["content"])["ticket"]
    critic = signed_by(director, "critic", ticket)
    assert not call(critic, "write_file", path="reviews/critica.md", content="referto").get("is_error")
    proof(critic, "critique")
    delivered = call(critic, "deliver", note="Il segno regge, verdetto READY.", verdict="READY")
    assert not delivered.get("is_error"), delivered
    accepted = call(director, "accept_ticket", ticket=ticket)
    assert not accepted.get("is_error"), accepted


def test_a_reviewer_who_repeats_a_check_does_not_unsign_the_other(tmp_path: Path) -> None:
    """On merlo3 the critic redid svg_audit after QA: the director could no longer accept the QA."""
    director = studio(tmp_path)
    tickets = {}
    for role, report_file in (("qa-inspector", "reviews/qa.md"), ("critic", "reviews/critica.md")):
        opened = open_review(
            director,
            role,
            title=f"Revisione {role}",
            outputs=["exports/segno.svg", report_file],
            checks={"*.svg": ["svg_audit"]},
        )
        tickets[role] = json.loads(opened["content"])["ticket"]
        reviewer = signed_by(director, role, tickets[role])
        call(reviewer, "write_file", path=report_file, content="referto")
        proof(reviewer, "svg_audit")
        delivered = call(reviewer, "deliver", note="Tutto regolare, verdetto READY.", verdict="READY")
        assert not delivered.get("is_error"), delivered
    for ticket in tickets.values():
        accepted = call(director, "accept_ticket", ticket=ticket)
        assert not accepted.get("is_error"), accepted


def hold_project_lock(path: Path) -> int:
    """Hold a project lock as another engine process would: through its own open file (`flock` conflicts)."""
    import fcntl
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def test_the_project_lock_lives_under_the_data_folder(tmp_path: Path) -> None:
    """COR-005: one lock file per project, beside the other engine data."""
    assert settings(tmp_path).layout.lock(ProjectName("forno")) == tmp_path / "data" / "locks" / "forno.lock"


@needs_craft
def test_a_second_process_cannot_work_on_the_same_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """COR-005: while one process holds the project, run, resume and decide are refused before any model
    call, any run row or any ledger write; once it lets go the same command works."""
    import os

    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno di quartiere", encoding="utf-8")
    transport = scripted_run(monkeypatch, [BLOCK_AT_ONCE])
    # A not-yet-existing project: the existence check sits behind the lock, so the refusal comes first.
    fd = hold_project_lock(tmp_path / "data" / "locks" / "forno.lock")
    try:
        capsys.readouterr()
        assert cli.main(["run", "forno", str(brief), "--budget", "12"]) == 1
        assert "già lavorando" in capsys.readouterr().out
        for command in (["resume", "forno"], ["decide", "forno", "--approve", "--text", "ok"]):
            assert cli.main(command) == 1
            assert "già lavorando" in capsys.readouterr().out
        assert transport.requests == []
        assert not path.exists() or Ledger(path).project("forno") is None
        assert not path.exists() or Ledger(path).runs("forno") == []
    finally:
        os.close(fd)
    # Released: the one worker proceeds and the transport sees its call only.
    assert cli.main(["run", "forno", str(brief), "--budget", "12"]) == 0
    assert len(transport.requests) == 1


def test_run_takes_the_lock_before_it_checks_that_the_project_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """COR-005: two `agency run` of one new name must not both pass the existence check, so a busy project is
    reported as busy even when the other process has already created it."""
    import os

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    fd = hold_project_lock(tmp_path / "data" / "locks" / "forno.lock")
    try:
        capsys.readouterr()
        assert cli.main(["run", "forno", str(tmp_path / "brief.md"), "--budget", "5"]) == 1
        out = capsys.readouterr().out
    finally:
        os.close(fd)
    assert "già lavorando" in out
    assert "esiste già" not in out


@pytest.mark.parametrize(
    "command",
    [
        ["verify"],
        ["runs", "forno"],
        ["artifacts", "forno"],
        ["compare", "1", "2"],
        ["report", "forno"],
        ["insights"],
        ["budget", "forno", "5"],
        ["resume", "forno"],
        ["decide", "forno", "--approve", "--text", "ok"],
        ["restore", "0123abcd", "copia.svg"],
        ["judge", "a.svg", "b.svg"],
    ],
    ids=lambda command: command[0],
)
def test_read_only_commands_never_create_a_registry(
    command: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong folder or data root is an error, not a fresh empty registry that reports on itself (DX-003)."""
    path = cli_data(tmp_path, monkeypatch)
    assert cli.main(command) == 1
    assert capsys.readouterr().out.splitlines() == [f"REGISTRO: nessun registro in {path.absolute()}"]
    assert not path.exists()


def busy_line(project: str) -> str:
    return f"Un altro processo sta già lavorando sul progetto {project}: attendi che finisca e riprova"


def test_budget_changes_the_cap_while_a_worker_holds_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F29, by design: raising the cap is how a running project is let finish, and the gateway reads the cap
    on every call, so `agency budget` takes no claim on the project."""
    import os

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    fd = hold_project_lock(tmp_path / "data" / "locks" / "forno.lock")
    try:
        assert cli.main(["budget", "forno", "40"]) == 0
    finally:
        os.close(fd)
    row = Ledger(path).project("forno")
    assert row is not None and row.budget_usd == 40.0
    assert capsys.readouterr().out.startswith("forno: budget portato a 40.00 $")


def test_migrate_refuses_while_a_worker_holds_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F30: the registry is rewritten only when no project is being worked on; the claims taken so far are
    let go again, and nothing is migrated or backed up."""
    import os

    from agency.process.session import ProjectLock

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    locks = tmp_path / "data" / "locks"
    locks.mkdir(parents=True)
    (locks / "aaa.lock").touch()  # claimed first, in name order, then let go on the refusal
    monkeypatch.setattr(cli, "migrate", lambda _: pytest.fail("migrated under a running worker"))
    fd = hold_project_lock(locks / "forno.lock")
    try:
        capsys.readouterr()
        assert cli.main(["migrate"]) == 1
    finally:
        os.close(fd)
    assert capsys.readouterr().out.splitlines() == [busy_line("forno")]
    assert not (tmp_path / "data" / "backups").exists()
    with ProjectLock(locks / "aaa.lock"), ProjectLock(locks / "forno.lock"):
        pass


def test_migrate_holds_every_project_until_the_migration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agency.ledger.schema import Migration
    from agency.process.session import ProjectBusy, ProjectLock

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    locks = tmp_path / "data" / "locks"
    locks.mkdir(parents=True)
    (locks / "forno.lock").touch()
    (locks / "notes.txt").touch()  # not a project lock
    during: list[str] = []

    def migrating(_: Path) -> Migration:
        try:
            with ProjectLock(locks / "forno.lock"):
                during.append("free")
        except ProjectBusy:
            during.append("held")
        return Migration("rev", None)

    monkeypatch.setattr(cli, "migrate", migrating)
    assert cli.main(["migrate"]) == 0
    assert during == ["held"]
    with ProjectLock(locks / "forno.lock"):  # let go once the migration has ended
        pass
    assert "già aggiornato" in capsys.readouterr().out


# 2.F63: a registry-wide claim, shared by run, resume and decide, exclusive for migrate

MIGRATING = "agency migrate sta aggiornando il registro: attendi che finisca e riprova"
REGISTRY_BUSY = "Un altro processo sta lavorando sul registro: attendi che finisca e riprova"
COMMANDS = {
    "run": ["run", "forno", "brief.md", "--budget", "5"],
    "resume": ["resume", "forno"],
    "decide": ["decide", "forno", "--approve", "--text", "ok"],
}


def test_the_registry_claim_lives_beside_the_project_claims(tmp_path: Path) -> None:
    assert settings(tmp_path).layout.registry_lock == tmp_path / "data" / "locks" / ".registry.lock"


@pytest.mark.parametrize("command", COMMANDS.values(), ids=COMMANDS.keys())
def test_run_resume_and_decide_refuse_while_a_migration_holds_the_registry(
    command: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F63: a first `run` of a new project has no project lock yet, so the migration's per-project claims
    cannot stop it; the registry claim does, before any session or model call."""
    import os

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr("agency.process.session.open_session", lambda *_, **__: pytest.fail("session opened"))
    fd = hold_project_lock(tmp_path / "data" / "locks" / ".registry.lock")  # exclusive, as `migrate` does
    try:
        capsys.readouterr()
        assert cli.main(command) == 1
    finally:
        os.close(fd)
    assert capsys.readouterr().out.splitlines() == [MIGRATING]


def test_a_project_named_registry_is_not_held_up_by_the_registry_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The registry claim has a dotted name, which no project name can have: it never shares a file."""
    cli_data(tmp_path, monkeypatch)
    assert cli._locked("registry", lambda: 0) == 0  # type: ignore[attr-defined]
    assert (
        settings(tmp_path).layout.lock(parse_project_name("registry"))
        != settings(tmp_path).layout.registry_lock
    )


def test_migrate_refuses_while_a_command_holds_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F63: a `run` holds the registry for the whole command, so a migration started during it refuses."""
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr(cli, "migrate", lambda _: pytest.fail("migrated under a running command"))
    during: list[int] = []

    def running(_: object) -> int:
        during.append(cli.main(["migrate"]))
        return 0

    monkeypatch.setattr(cli, "_run_locked", running)
    capsys.readouterr()
    assert cli.main(COMMANDS["run"]) == 0
    assert during == [1]
    assert capsys.readouterr().out.splitlines() == [busy_line("forno")]  # the first project it finds busy


def test_migrate_refuses_while_the_registry_is_shared_and_no_project_is_known_busy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F63: a first `run` of a new project holds the registry but has no project lock file yet."""
    import os

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr(cli, "migrate", lambda _: pytest.fail("migrated under a running command"))
    fd = hold_shared(tmp_path / "data" / "locks" / ".registry.lock")
    try:
        capsys.readouterr()
        assert cli.main(["migrate"]) == 1
    finally:
        os.close(fd)
    assert capsys.readouterr().out.splitlines() == [REGISTRY_BUSY]


def test_migrate_names_the_busy_project_when_a_command_holds_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import os

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    locks = tmp_path / "data" / "locks"
    monkeypatch.setattr(cli, "migrate", lambda _: pytest.fail("migrated under a running command"))
    held = [hold_shared(locks / ".registry.lock"), hold_project_lock(locks / "forno.lock")]
    try:
        capsys.readouterr()
        assert cli.main(["migrate"]) == 1
    finally:
        for fd in held:
            os.close(fd)
    assert capsys.readouterr().out.splitlines() == [busy_line("forno")]


def hold_shared(path: Path) -> int:
    import fcntl
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_SH)
    return fd


def test_commands_on_different_projects_share_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The registry claim is shared: a command on another project is not held up by the first one."""
    cli_data(tmp_path, monkeypatch)
    seen: list[int] = []

    def running(args: object) -> int:
        if getattr(args, "project", "") == "forno":
            seen.append(cli.main(["run", "altro", "brief.md", "--budget", "5"]))
        return 0

    monkeypatch.setattr(cli, "_run_locked", running)
    assert cli.main(COMMANDS["run"]) == 0
    assert seen == [0]


def test_migrate_holds_the_registry_until_the_migration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2.F63: the claim is taken before the rewrite and let go after it; the registry's own file is not
    mistaken for a project's."""
    from agency.ledger.schema import Migration
    from agency.process.session import ProjectBusy, ProjectLock

    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    registry = tmp_path / "data" / "locks" / ".registry.lock"
    registry.parent.mkdir(parents=True)
    registry.touch()  # left by an earlier command
    during: list[str] = []

    def migrating(_: Path) -> Migration:
        try:
            with ProjectLock(registry, shared=True):
                during.append("free")
        except ProjectBusy:
            during.append("held")
        return Migration("rev", None)

    monkeypatch.setattr(cli, "migrate", migrating)
    assert cli.main(["migrate"]) == 0
    assert during == ["held"]
    with ProjectLock(registry):
        pass


def test_a_shared_claim_lets_other_shared_claims_in_and_keeps_an_exclusive_one_out(tmp_path: Path) -> None:
    from agency.process.session import ProjectBusy, ProjectLock

    path = tmp_path / "locks" / ".registry.lock"
    with ProjectLock(path, shared=True), ProjectLock(path, shared=True), pytest.raises(ProjectBusy):
        ProjectLock(path).__enter__()
    with ProjectLock(path), pytest.raises(ProjectBusy):
        ProjectLock(path, shared=True).__enter__()


@pytest.mark.parametrize("command", [["run", "forno", "brief.md", "--budget", "5"], ["resume", "forno"]])
def test_run_and_resume_stop_before_the_session_when_the_sandbox_has_no_scope(
    command: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F43: without a capped scope every tool call would be refused; stop before any model call."""
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr(cli, "scope_problem", lambda: "niente sessione systemd")
    monkeypatch.setattr("agency.process.session.open_session", lambda *_, **__: pytest.fail("session opened"))
    assert cli.main(command) == 1
    assert capsys.readouterr().out.splitlines() == [
        "SANDBOX NON DISPONIBILE: niente sessione systemd. agency doctor dice come sistemarla"
    ]


def test_decide_stops_before_the_session_when_the_sandbox_has_no_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr(cli, "scope_problem", lambda: "niente sessione \x1b[2Jsystemd")
    monkeypatch.setattr("agency.process.session.open_session", lambda *_, **__: pytest.fail("session opened"))
    assert cli.main(["decide", "forno", "--approve", "--text", "ok"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "SANDBOX NON DISPONIBILE: niente sessione [2Jsystemd. agency doctor dice come sistemarla"
    ]


def test_run_with_no_sandbox_scope_creates_no_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "scope_problem", lambda: "niente")
    transport = scripted_run(monkeypatch, [BLOCK_AT_ONCE])
    assert cli.main(["run", "forno", str(tmp_path / "brief.md"), "--budget", "5"]) == 1
    assert transport.requests == []
    assert not path.exists()


def test_a_relative_toolchain_dir_is_refused_like_the_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2.F36: the sandbox binds the toolchain folder as given, so a relative one would name a different folder
    from each current folder."""
    line = (
        "AGENCY_TOOLCHAIN_DIR deve essere un percorso assoluto, non 'toolchain': uno relativo dipende dalla"
        " cartella da cui parte il comando"
    )
    monkeypatch.setenv("AGENCY_TOOLCHAIN_DIR", "toolchain")
    with pytest.raises(RelativeDataRoot) as refused:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert str(refused.value) == line
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out == line + "\n"
    monkeypatch.setenv("AGENCY_TOOLCHAIN_DIR", str(tmp_path))
    assert Settings(_env_file=None).toolchain_dir == tmp_path  # type: ignore[call-arg]
    monkeypatch.delenv("AGENCY_TOOLCHAIN_DIR")
    assert Settings(_env_file=None).toolchain_dir.is_absolute()  # type: ignore[call-arg]


# Model text: it reaches the operator's terminal without control sequences (SEC-009)

OSC_52 = "\x1b]52;c;ZWNobyBwd25lZA==\x07"


def test_cli_strips_control_sequences_from_model_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gate = ConceptGate(
        ticket="T-0001",
        files=["tavola\x1b[31m.pdf"],
        options=["V", "X\x1b[2J"],
        recommended="V\x07",
        reasons=f"scelgo B{OSC_52} perché\x1b[2J regge",
    )
    session = FakeSession([gate], Ledger(tmp_path / "l.sqlite"))
    monkeypatch.setattr(cli, "_report_of", lambda *_: None)
    monkeypatch.setattr(report, "render", lambda _: "rapporto")
    project = parse_project_name("officina")
    assert cli._guarded(project, session, lambda: "bloccato: fermo\x1b[2J qui") == 0  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "scelgo B" in out
    assert "regge" in out
    assert "Esito: bloccato: fermo" in out
    assert "tavola" in out


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("a\nb\tc", "a\nb\tc"),
        ("perché è così, 5 €", "perché è così, 5 €"),
        ("logo 🎨", "logo 🎨"),
        ("a\x00b", "ab"),
        ("a\x07b", "ab"),
        ("a\x1b[2Jb", "a[2Jb"),
        ("a\x7fb", "ab"),
        ("a\x85b", "ab"),
        ("a\x9b2Jb", "a2Jb"),
        ("a\rb", "ab"),
    ],
)
def test_plain_drops_control_characters_and_keeps_text(raw: str, kept: str) -> None:
    assert report.plain(raw) == kept


def test_a_report_filters_the_model_text_it_renders(
    tmp_path: Path, report_of: Callable[[Path, str], ProjectReport]
) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.open(spec(title="Segno\x1b[31m rosso\x9b2J"), "p")
    out = report.render(report_of(tmp_path / "l.sqlite", "p"))
    assert "\x1b" not in out
    assert "\x9b" not in out
    assert "Segno[31m rosso2J" in out
    assert len(out.splitlines()) > 5  # newlines survive


def _run_row(seq: int, command: str) -> RunRow:
    fingerprint = Fingerprint(
        model="",
        effort="",
        explorer_effort="",
        proposal_effort="",
        explorers=1,
        max_parallel=1,
        prompts={},
        registry={},
        code={},
        lock="",
        python="3",
        tools={},
    )
    return RunRow(
        seq=seq,
        at="2026-11-01",
        project="p",
        command=command,
        digest="d" * 64,
        fingerprint_json=fingerprint.model_dump_json(),
    )


def _artifact_row(path: str) -> ArtifactRow:
    return ArtifactRow(
        at="2026-11-01",
        sha256="a" * 64,
        project="p",
        path=path,
        ticket_id="T-1",
        origin="consegna",
        media_type="text/plain",
        size=3,
    )


def _judgment_row(file: str) -> JudgmentRow:
    return JudgmentRow(
        at="2026-11-01",
        comparison="c1",
        judge="andrea",
        letter="A",
        project="p",
        file=file,
        sha256="a" * 64,
        level="buono",
        specific=True,
        best=True,
        why="",
    )


class _RunsLedger:
    def runs(self, _: str) -> list[RunRow]:
        return [_run_row(1, "run\x1b[31m"), _run_row(2, "resume\x07")]


def _provenance() -> Provenance:
    return Provenance(
        built_at="t",
        sources=[],
        registry_revision="r\x1b[31m",
        calls=1,
        from_registry=1,
        from_traces=0,
        unmeasured=0,
        phases_recorded=0,
        phases_derived=0,
        unreadable_trace_lines=0,
        unreadable_transcript_lines=0,
    )


RENDERERS: dict[str, Callable[[], str]] = {
    "runs": lambda: report.render_runs(_RunsLedger(), "p"),  # type: ignore[arg-type]
    "comparison": lambda: report.render_comparison(_run_row(1, "run\x1b[31m"), _run_row(2, "run\x07")),
    "reveal": lambda: report.render_reveal([_judgment_row("segno\x1b[31m.svg")]),
    "artifacts": lambda: report.render_artifacts([_artifact_row("segno\x1b[31m.svg")], "p"),
    "restored": lambda: report.render_restored([_artifact_row("segno\x1b[31m.svg")], "dest\x07"),
    "damaged": lambda: report.render_damaged([_artifact_row("segno\x1b[31m.svg")]),
    "provenance": lambda: report.render_provenance(_provenance(), "path\x1b[31m"),
}


@pytest.mark.parametrize("name", RENDERERS)
def test_every_report_renderer_filters_control_characters(name: str) -> None:
    out = RENDERERS[name]()
    assert "\x1b" not in out
    assert "\x07" not in out
    assert out.strip()


def judge_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.chdir(tmp_path)
    Ledger(tmp_path / "data" / "ledger.sqlite")  # `judge` needs a registry to exist
    first, second = tmp_path / "a.svg", tmp_path / "b.svg"
    first.write_text("<svg>1</svg>", encoding="utf-8")
    second.write_text("<svg>2</svg>", encoding="utf-8")
    return [str(first), str(second)]


def test_judge_filters_the_refusal_of_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    judge_setup(tmp_path, monkeypatch)
    assert cli.main(["judge", "manca\x1b[2J.svg", "altro.svg"]) == 1
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "manca[2J.svg" in out


def test_judge_lays_the_anonymous_copies_out_under_the_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The copies a blind judgment shows live in `<data root>/blind/<comparison>`, one folder each. The
    command names the folder before the judgment, and removes it when the judgment stops."""
    paths = judge_setup(tmp_path, monkeypatch)
    laid_out: list[Path] = []

    def stop(*_: object) -> None:
        laid_out.extend((tmp_path / "data" / "blind").glob("*/*.svg"))
        raise CannotCompare("fermato dopo la disposizione")

    monkeypatch.setattr("agency.evaluation.board.lay_board", lambda *_: None)
    monkeypatch.setattr("agency.evaluation.blind.interview", stop)
    assert cli.main(["judge", *paths]) == 1
    assert len(laid_out) == 2
    (folder,) = {copy.parent for copy in laid_out}
    assert f"nella cartella {folder.resolve()}:" in capsys.readouterr().out


def test_judge_filters_a_refusal_after_the_copies_are_laid_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = judge_setup(tmp_path, monkeypatch)

    def refuse(*_: object) -> None:
        raise CannotCompare("non si rende\x1b[2J \x07")

    monkeypatch.setattr("agency.evaluation.board.lay_board", lambda *_: None)
    monkeypatch.setattr("agency.evaluation.blind.interview", refuse)
    assert cli.main(["judge", *paths]) == 1
    out = capsys.readouterr().out
    assert "Nulla registrato" in out
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "non si rende" in out


# The agent tools reach the work folder only through the no-follow helpers (2.F9-2.F11), the critic's
# ratings live where only the harness writes (2.F24) and the pages to check come from the draft (2.F26)

SECRET = "contenuto riservato del cliente"
WHY = "Il segno tondo regge alla dimensione d'uso, quello a doppio filo si impasta e perde la figura."


def use(ctx: ToolContext, name: str, **arguments: object) -> dict:
    """One call of one tool, whatever the role's set holds."""
    return Toolbox(ctx, [TOOLS[name]]).call(f"t{next(OPERATIONS)}", name, arguments)


WHERE = pytest.mark.parametrize("where", ["outside", "inside"])


def host_folder(tmp_path: Path, where: str, ctx: ToolContext) -> Path:
    """A folder with a file the work must never read or change: outside the work folder, or in it (a link
    to a neighbour's files stays inside the perimeter, so `inside()` lets it through)."""
    host = tmp_path / "host-folder" if where == "outside" else ctx.work / "altrove"
    host.mkdir(parents=True)
    (host / "segreto.txt").write_text(SECRET, encoding="utf-8")
    return host


def untouched(host: Path) -> bool:
    names = sorted(path.name for path in host.iterdir())
    return names == ["segreto.txt"] and (host / "segreto.txt").read_text(encoding="utf-8") == SECRET


def director(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "design-director", "T-0")
    ctx.settings = settings(tmp_path)
    ctx.ticket_id = ctx.ledger.open(spec(type=TicketType.DELIVERY, assignee="design-director"), "p")
    return ctx


PLAN: dict[str, Any] = {
    "levers": [{"lever": "il nome"}, {"lever": "il gesto"}],
    "assets": ["forno"],
    "excluded": ["la spiga", "il cerchio", "il fumo"],
    "applications": [{"name": "insegna", "size": "16 mm"}, {"name": "scatola", "size": "4 cm"}],
}


@WHERE
def test_plan_exploration_never_writes_the_plan_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")
    (ctx.work / "explorations").symlink_to(host, target_is_directory=True)

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_plan_exploration_never_makes_an_explorer_folder_through_a_planted_link(
    tmp_path: Path, where: str
) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")
    (ctx.work / "explorations/r1").mkdir(parents=True)
    (ctx.work / "explorations/r1/a").symlink_to(host, target_is_directory=True)

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_plan_exploration_never_copies_a_linked_brief_to_an_explorer(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").symlink_to(host / "segreto.txt")

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert not list(ctx.work.glob("explorations/r1/*/brief.md"))
    assert untouched(host)


CARD = ConceptCard(
    concept="Il forno come casa", client_fact="f", why_not_obvious="w", drawing="d", substitution="s"
)


def sketcher(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "direction-a", "T-0")
    ctx.settings = settings(tmp_path)
    sketch = spec(
        type=TicketType.SKETCH,
        assignee="direction-a",
        outputs=["scheda.json", "schizzo-a.png"],
        checks={"*.png": ["visual_review"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.VECTOR],
    )
    ctx.ticket_id = ctx.ledger.open(sketch, "p")
    return ctx


@WHERE
def test_submit_concept_never_writes_the_card_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = sketcher(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "scheda.json").symlink_to(host / "segreto.txt")

    use(ctx, "submit_concept", **CARD.model_dump())

    assert untouched(host)


def rating(*letters: str, passing: str = "") -> list[dict]:
    return [{"letter": letter, "first_look": "Un segno", "passes": letter in passing} for letter in letters]


def board_critic(tmp_path: Path) -> ToolContext:
    """The critic of round 1: its work folder is the board's, inside the project's."""
    ctx = context(tmp_path, "critic", "T-5")
    ctx.settings = settings(tmp_path)
    ctx.sandbox = Sandbox(ctx.work / "board/r1", ops=ctx.sandbox.ops)
    ctx.sandbox.work.mkdir(parents=True)
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptRow(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    return ctx


def selector(critic: ToolContext) -> ToolContext:
    """The director who chooses: same project and ledger, the work folder above the board."""
    ctx = ToolContext(
        "design-director",
        "p",
        "T-1",
        "j",
        critic.ledger,
        Sandbox(critic.work.parent.parent),
        CommandIndex([]),
        critic.artifacts,
        settings=critic.settings,
    )
    return ctx


@WHERE
def test_rate_board_never_writes_the_rating_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = board_critic(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "reviews").symlink_to(host, target_is_directory=True)

    result = use(ctx, "rate_board", ratings=rating("X", "Y", passing="X"))

    assert result.get("is_error"), result
    assert untouched(host)


def test_select_concepts_ignores_a_rating_forged_in_the_work_folder(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    chooser = selector(critic)
    forged = json.dumps(rating("X", "Y", passing="XY"))
    assert not use(critic, "write_file", path="reviews/valutazione.json", content=forged).get("is_error")

    result = use(chooser, "select_concepts", chosen=["X"], reasons="r")

    assert result.get("is_error"), result
    assert "la tavola del giro 1 non è stata valutata con rate_board" in result["content"]


def test_select_concepts_lets_through_only_what_rate_board_recorded(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    chooser = selector(critic)
    assert not use(critic, "rate_board", ratings=rating("X", "Y", passing="X")).get("is_error")
    forged = json.dumps(rating("X", "Y", passing="XY"))
    assert not use(critic, "write_file", path="reviews/valutazione.json", content=forged).get("is_error")

    refused = use(chooser, "select_concepts", chosen=["Y"], reasons="r")
    chosen = use(chooser, "select_concepts", chosen=["X"], reasons="r")

    assert refused.get("is_error") and "primo sguardo" in refused["content"]
    assert not chosen.get("is_error"), chosen


def test_rate_board_still_writes_the_ticket_output_and_the_harness_copy(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    ratings = rating("X", "Y", passing="X")

    assert not use(critic, "rate_board", ratings=ratings).get("is_error")

    assert json.loads((critic.work / "reviews/valutazione.json").read_text(encoding="utf-8")) == ratings
    assert critic.settings is not None
    kept = critic.settings.layout.ratings(ProjectName("p"), 1)
    assert kept == critic.settings.layout.root / "ops" / "p" / "ratings-r1.json"
    assert json.loads(kept.read_text(encoding="utf-8")) == ratings


def proposal_ready(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "design-director", "T-0")
    ctx.settings = settings(tmp_path)
    open_idea(
        ctx.ledger,
        ConceptRow(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"),
    )
    folder = ctx.work / "proposals/r1/x"
    folder.mkdir(parents=True)
    Image.new("RGB", (300, 200), (20, 20, 20)).save(folder / "proposta-x.png")
    return ctx


DRAFT: dict[str, Any] = {
    "proposals": [{"letter": "X", "title": "T", "idea": "I", "why": "W", "risk": "R"}],
    "recommended": "X",
    "reasons": "r",
}


@WHERE
def test_draft_presentation_never_writes_the_pages_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = proposal_ready(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "presentation").symlink_to(host, target_is_directory=True)

    result = use(ctx, "draft_presentation", **DRAFT)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_draft_presentation_never_writes_the_texts_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = proposal_ready(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "presentation/r1").mkdir(parents=True)
    (ctx.work / "presentation/r1/testi.json").symlink_to(host / "segreto.txt")

    use(ctx, "draft_presentation", **DRAFT)

    assert untouched(host)


def drafted(tmp_path: Path) -> tuple[ToolContext, list[str]]:
    ctx = proposal_ready(tmp_path)
    done = use(ctx, "draft_presentation", **DRAFT)
    assert not done.get("is_error"), done
    return ctx, json.loads(done["content"])["pagine"]


def view_all(ctx: ToolContext, pages: list[str]) -> None:
    for page in pages:
        assert not use(ctx, "view_image", path=page).get("is_error")


@WHERE
def test_present_concepts_never_sends_a_linked_draft(tmp_path: Path, where: str) -> None:
    ctx, pages = drafted(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    view_all(ctx, pages)
    (ctx.work / "presentation/r1/testi.json").unlink()
    (ctx.work / "presentation/r1/testi.json").symlink_to(host / "segreto.txt")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert SECRET not in str(result)
    assert ctx.finished is None


def test_present_concepts_checks_the_pages_of_the_draft_and_only_those(tmp_path: Path) -> None:
    ctx, pages = drafted(tmp_path)
    Image.new("RGB", (50, 50), (200, 0, 0)).save(ctx.work / "presentation/r1/pagina-99.png")
    view_all(ctx, pages)

    result = use(ctx, "present_concepts")

    assert not result.get("is_error"), result
    assert ctx.finished is not None


def test_present_concepts_refuses_a_page_of_the_draft_that_is_gone(tmp_path: Path) -> None:
    ctx, pages = drafted(tmp_path)
    view_all(ctx, pages)
    (ctx.work / pages[-1]).unlink()

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert pages[-1] in result["content"]
    assert ctx.finished is None


@WHERE
def test_present_concepts_refuses_a_page_that_became_a_link(tmp_path: Path, where: str) -> None:
    ctx, pages = drafted(tmp_path)
    view_all(ctx, pages)
    page, host = ctx.work / pages[0], host_folder(tmp_path, where, ctx)
    (host / "pagina.png").write_bytes(page.read_bytes())
    page.unlink()
    page.symlink_to(host / "pagina.png")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert ctx.finished is None


def seen_image(tmp_path: Path, where: str) -> ToolContext:
    """An image the agent has viewed, then swapped for a link to a host file with the same bytes."""
    ctx = context(tmp_path, "critic")
    host = host_folder(tmp_path, where, ctx)
    image = ctx.work / "segno.png"
    Image.new("RGB", (60, 60), (20, 20, 20)).save(image)
    assert not use(ctx, "view_image", path="segno.png").get("is_error")
    (host / "fuori.png").write_bytes(image.read_bytes())
    image.unlink()
    image.symlink_to(host / "fuori.png")
    return ctx


@WHERE
def test_a_proof_that_became_a_link_is_not_the_version_that_was_seen(tmp_path: Path, where: str) -> None:
    """`evidence.record` refuses a link too, but the proof is picked first: its hash is not a target's."""
    ctx = seen_image(tmp_path, where)

    with pytest.raises(OutsidePerimeter):
        _seen_proof(ctx, "segno.png")


@WHERE
def test_judge_does_not_compare_against_a_link(tmp_path: Path, where: str) -> None:
    ctx = context(tmp_path, "critic")
    host = host_folder(tmp_path, where, ctx)
    Image.new("RGB", (60, 60), (20, 20, 20)).save(ctx.work / "segno.png")
    Image.new("RGB", (60, 60), (200, 20, 20)).save(host / "altro.png")
    (ctx.work / "altro.png").symlink_to(host / "altro.png")
    assert not use(ctx, "view_image", path="segno.png").get("is_error")

    result = use(ctx, "judge", file="segno.png", compare=["altro.png"], why=WHY, result="PASS")

    assert result.get("is_error"), result
    assert "inesistenti" in result["content"]


@WHERE
def test_open_ticket_does_not_take_a_link_as_an_input(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "riferimento.txt").symlink_to(host / "segreto.txt")

    result = use(
        ctx,
        "open_ticket",
        title="Segno",
        request="Disegna",
        type="produzione",
        assignee="identity-designer",
        outputs=["a.md"],
        checks={"*.md": ["req:testo"]},
        media=["nessuno"],
        medium_why="solo testo, nessun mezzo visivo",
        inputs=["riferimento.txt"],
    )

    assert result.get("is_error"), result
    assert "input inesistenti" in result["content"]


@WHERE
def test_deliver_never_hashes_an_output_that_is_a_link(tmp_path: Path, where: str) -> None:
    ctx = context(tmp_path, "identity-designer")
    host = host_folder(tmp_path, where, ctx)
    ctx.ticket_id = ctx.ledger.open(spec(), "p")
    (ctx.work / "a.md").write_text("nota", encoding="utf-8")
    evidence.record(
        ctx.ledger, ctx.work, "p", "a.md", "req:testo", "PASS", ctx.actor, ctx.ticket_id, note="ok"
    )
    (ctx.work / "a.md").unlink()
    (ctx.work / "a.md").symlink_to(host / "segreto.txt")

    result = use(ctx, "deliver", note="Consegnato.", verdict=None)

    assert result.get("is_error"), result
    assert ctx.finished is None


def test_is_file_under_is_true_only_for_a_regular_file_that_is_not_a_link(tmp_path: Path) -> None:
    work, host = tmp_path / "work", host_folder(tmp_path, "outside", context(tmp_path))
    (work / "dentro").mkdir()
    (work / "dentro/a.txt").write_text("a", encoding="utf-8")
    (work / "link.txt").symlink_to(work / "dentro/a.txt")
    (work / "cartella-link").symlink_to(host, target_is_directory=True)
    os.mkfifo(work / "tubo")

    assert is_file_under(work, "dentro/a.txt")
    assert not is_file_under(work, "dentro")  # a folder
    assert not is_file_under(work, "link.txt")  # a link, even to a file inside
    assert not is_file_under(work, "cartella-link/segreto.txt")  # a link on the way
    assert not is_file_under(work, "tubo")  # not a regular file, and it does not block
    assert not is_file_under(work, "manca.txt")
    for outside in ("dentro/../dentro/a.txt", "/etc/passwd", ""):
        with pytest.raises(OutsidePerimeter):
            is_file_under(work, outside)


def test_judge_refuses_a_file_compared_with_itself_under_another_spelling(tmp_path: Path) -> None:
    ctx = context(tmp_path, "critic")
    Image.new("RGB", (60, 60), (20, 20, 20)).save(ctx.work / "segno.png")
    assert not use(ctx, "view_image", path="segno.png").get("is_error")

    result = use(ctx, "judge", file="segno.png", compare=["./segno.png"], why=WHY, result="PASS")

    assert result.get("is_error"), result
    assert "con se stesso" in result["content"]


def test_present_concepts_refuses_a_draft_nobody_made(tmp_path: Path) -> None:
    ctx = proposal_ready(tmp_path)
    (ctx.work / "presentation/r1").mkdir(parents=True)
    Image.new("RGB", (50, 50), (200, 0, 0)).save(ctx.work / "presentation/r1/pagina-1.png")
    (ctx.work / "presentation/r1/testi.json").write_text(json.dumps({"planted": True}), encoding="utf-8")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert "draft_presentation" in result["content"]
    assert ctx.finished is None


def test_present_concepts_checks_the_pages_of_the_latest_draft(tmp_path: Path) -> None:
    ctx, first = drafted(tmp_path)
    two = {**DRAFT, "proposals": [*DRAFT["proposals"], {**DRAFT["proposals"][0], "letter": "Y"}]}
    open_idea(
        ctx.ledger,
        ConceptRow(project="p", round=1, letter="b", lever="l", idea_ticket="", anon="Y", status="proposta"),
    )
    (ctx.work / "proposals/r1/y").mkdir()
    Image.new("RGB", (300, 200), (20, 20, 20)).save(ctx.work / "proposals/r1/y/proposta-y.png")
    second = json.loads(use(ctx, "draft_presentation", **two)["content"])["pagine"]
    assert len(second) > len(first)
    view_all(ctx, first)

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert ctx.finished is None


# 2.F49: the layout's project paths take a checked name, and the tools parse the context's text first


@pytest.mark.parametrize("method", ["lock", "ops_inputs", "ops_records", "ratings"])
def test_the_layout_builds_project_paths_only_from_a_checked_name(method: str) -> None:
    """The type carries the rule: a `str` that skipped `parse_project_name` is a pyright error at the call."""
    import typing

    from agency.contracts.layout import DataLayout

    assert typing.get_type_hints(getattr(DataLayout, method))["project"] is ProjectName


def evil_project(ctx: ToolContext, name: str = "../outside") -> ToolContext:
    ctx.settings = settings(ctx.work.parent)
    ctx.project = name
    open_idea(
        ctx.ledger,
        ConceptRow(project=name, round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"),
    )
    return ctx


def test_rate_board_refuses_a_project_name_that_would_leave_the_ops_folder(tmp_path: Path) -> None:
    ctx = evil_project(board_critic(tmp_path))

    result = use(ctx, "rate_board", ratings=rating("X", passing="X"))

    assert result.get("is_error"), result
    assert "nome di progetto non valido" in result["content"]
    assert not (tmp_path / "data" / "outside").exists()


def test_select_concepts_refuses_a_project_name_that_would_leave_the_ops_folder(tmp_path: Path) -> None:
    ctx = evil_project(board_critic(tmp_path))

    result = use(ctx, "select_concepts", chosen=["X"], reasons="r")

    assert result.get("is_error"), result
    assert "nome di progetto non valido" in result["content"]


def test_craft_run_refuses_a_project_name_that_would_leave_the_ops_folder(tmp_path: Path) -> None:
    ctx = evil_project(context(tmp_path))
    ctx.sandbox = IdleSandbox(ctx.work, ops=ctx.sandbox.ops)
    ctx.index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])

    result = use(ctx, "craft_run", document="segno.vectorcraft", steps=[{"command": "path.create"}])

    assert result.get("is_error"), result
    assert "nome di progetto non valido" in result["content"]


# 2.F64: the CLI's one-line messages stay on one line whatever the outside text holds


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("a\nb", "a b"),
        ("a\r\nb\tc", "a b c"),
        ("a\rb", "a b"),
        ("a\n\n\t\rb", "a b"),
        ("\n  a b  \n", "a b"),
        ("a\x1b[2Jb\x07", "a[2Jb"),
        ("perché è così", "perché è così"),
    ],
)
def test_one_line_folds_every_line_break_and_tab_to_a_space(raw: str, folded: str) -> None:
    from agency.contracts.text import one_line

    assert one_line(raw) == folded


def test_an_api_error_body_with_a_newline_stays_on_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def fail() -> None:
        raise anthropic.APIError("proxy\nSANDBOX NON DISPONIBILE: finto\tbody\r\nfine", request, body=None)

    assert cli._guarded(ProjectName("officina"), session, fail) == 3  # type: ignore[arg-type]
    lines = [line for line in capsys.readouterr().out.splitlines() if line]
    assert lines == [
        "API NON DISPONIBILE: proxy SANDBOX NON DISPONIBILE: finto body fine. Il lavoro è salvato.",
        "Per riprendere: agency resume officina",
    ]


def test_a_sandbox_refusal_with_a_newline_stays_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agency.workshop.sandbox import SandboxUnavailable

    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    monkeypatch.setattr(cli, "_report_of", lambda *_: None)
    monkeypatch.setattr(report, "render", lambda _: "rapporto")

    def fail() -> None:
        raise SandboxUnavailable("systemd\nBUDGET FINITO: finto")

    assert cli._guarded(ProjectName("officina"), session, fail) == 4  # type: ignore[arg-type]
    lines = capsys.readouterr().out.splitlines()
    assert "SANDBOX NON DISPONIBILE: systemd BUDGET FINITO: finto. Il lavoro è salvato." in lines


def test_the_sandbox_preflight_refusal_stays_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = cli_data(tmp_path, monkeypatch)
    Ledger(path).set_project("forno", 12.0)
    monkeypatch.setattr(cli, "scope_problem", lambda: "niente sessione\nsystemd\tdice no")
    assert cli.main(["resume", "forno"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "SANDBOX NON DISPONIBILE: niente sessione systemd dice no. agency doctor dice come sistemarla"
    ]


def test_the_first_judge_refusal_with_a_newline_stays_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = judge_setup(tmp_path, monkeypatch)

    def refuse(*_: object) -> None:
        raise CannotCompare("prima\nriga")

    monkeypatch.setattr("agency.evaluation.blind.candidates", refuse)
    assert cli.main(["judge", *paths]) == 1
    assert capsys.readouterr().out.splitlines() == ["Confronto non possibile: prima riga"]


def test_the_judge_refusal_after_the_copies_with_a_newline_stays_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = judge_setup(tmp_path, monkeypatch)

    def refuse(*_: object) -> None:
        raise CannotCompare("seconda\r\nriga")

    monkeypatch.setattr("agency.evaluation.board.lay_board", lambda *_: None)
    monkeypatch.setattr("agency.evaluation.blind.interview", refuse)
    assert cli.main(["judge", *paths]) == 1
    last = capsys.readouterr().out.splitlines()[-1]
    assert last == "Confronto non possibile: seconda riga. Nulla registrato"
