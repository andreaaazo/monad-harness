"""Defects found by rereading the system before M2: the perimeter, ticket paths, delegations, resume and the
loop."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from agency.agents.loop import AgentRunner
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Status, TicketSpec, TicketType
from agency.gateway import ModelGateway
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop import craft
from agency.workshop.craft import Command, CommandIndex
from support.hardening import IdleSandbox, call, context, spec
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)
from support.rules import RULES
from support.scripted import ScriptedTransport
from support.settings import settings

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
            ModelGateway(transport, ledger, config),
            ledger,
            config,
            index,
            FileStore(config.layout.artifacts),
            rules=RULES,
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
