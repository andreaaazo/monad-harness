"""Difetti trovati rileggendo il sistema prima di M2: ognuno ha qui la sua prova."""

from __future__ import annotations

import itertools
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest

from agency import cli
from agency.agents.loop import AgentRunner
from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.gate import ConceptGate, Gate
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.gateway import ModelGateway, ScriptedTransport
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from agency.ledger.models import EvidenceRow, UsageRow
from agency.qa import checks as qa
from agency.qa import delivery, evidence
from agency.telemetry import report
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import Sandbox
from agency.tools.surface import Toolbox, ToolContext, role_tools


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "projects", _env_file=None)  # type: ignore[call-arg]


def context(tmp_path: Path, actor: str = "identity-designer", ticket: str = "T-1") -> ToolContext:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return ToolContext(
        actor,
        "p",
        ticket,
        "i",
        Ledger(tmp_path / "l.sqlite"),
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
    )


OPERATIONS = itertools.count(1)


def call(ctx: ToolContext, tool_name: str, **arguments: object) -> dict:
    """Ogni chiamata ha il suo id: con lo stesso id il sistema ripete il primo esito, com'è giusto."""
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


# Perimetro


@pytest.mark.parametrize("name", ["../..", "../../.", "logo-design/../../.."])
def test_read_skill_cannot_leave_the_skills(tmp_path: Path, name: str) -> None:
    """La chiave API sta nella radice della repo: `name` non deve arrivarci."""
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


# Deleghe


def test_ticket_to_a_role_not_yet_ported_is_refused(tmp_path: Path) -> None:
    """Senza prompt il ruolo farebbe cadere il lavoro quando tocca a lui."""
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


# Ripresa


def test_transcript_survives_a_torn_last_line(tmp_path: Path) -> None:
    first = Transcript(tmp_path / "t.jsonl")
    first.append({"role": "user", "content": "uno"})
    with first.path.open("a", encoding="utf-8") as handle:
        handle.write('{"message": {"role": "assis')  # processo ucciso a metà riga
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
    """Il Replay lega ogni turno alla sua riga di usage col request_id; la ripresa legge solo i messaggi."""
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
    """Il progetto `p` con il tetto che il cliente dichiarerebbe: senza, il gateway non spende (ADR-0043)."""
    ledger = Ledger(config.ledger_path)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(responses)
    index = CommandIndex([])
    return (
        AgentRunner(
            ModelGateway(transport, ledger, config), ledger, config, index, FileStore(config.artifacts_dir)
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
    """Il promemoria non è una tacca: chi ha ripreso a lavorare non viene bloccato alla prima pausa."""
    done = reply(text("Fatto"), stop="end_turn")
    work = reply(tool("list_files", "l1"))
    run, _, ledger = runner(
        settings(tmp_path), [done, work, done, reply(tool("block", "b1", reason="ora mi fermo"))]
    )
    ticket = ledger.open(spec(), "p")
    outcome = run.run(ticket)
    assert outcome.note == "ora mi fermo"


def test_nothing_runs_after_the_tool_that_closes_the_ticket(tmp_path: Path) -> None:
    """Scrivere dopo la consegna renderebbe il lavoro diverso da ciò che è stato consegnato."""
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
    assert not (settings(tmp_path).project_dir("p") / "work/tardi.md").exists()


def paused() -> dict:
    block = {"type": "server_tool_use", "id": "srv1", "name": "web_search", "input": {"query": "merli"}}
    return reply(block, stop="pause_turn")


def test_paused_turn_resends_the_history_as_it_is(tmp_path: Path) -> None:
    """Le ricerche web si fermano così: niente messaggi aggiunti, il server riprende da solo."""
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
    """Una conversazione non può ripartire da una risposta di testo: sarebbe rifiutata dall'API."""
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


# Registro


def test_parallel_writers_never_hit_a_locked_database(tmp_path: Path) -> None:
    """Cinque esploratori scrivono insieme: leggere e poi scrivere non deve mai fallire."""
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
    """Due lavori lanciati insieme sono due processi: il lucchetto interno non basta."""
    path = tmp_path / "l.sqlite"
    errors: list[Exception] = []
    start = threading.Barrier(4)

    def work(project: str) -> None:
        try:
            start.wait(timeout=20)
            ledger = Ledger(path)  # ogni istanza ha il suo lucchetto, come un altro processo
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


# Prove


def test_a_crashed_measure_is_not_evidence(tmp_path: Path) -> None:
    (tmp_path / "segno.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"></svg>')
    outcome = qa.execute(Sandbox(tmp_path, settings(tmp_path).toolchain_dir), "optical_check", "segno.svg")
    assert outcome.result == "FAIL"
    assert not outcome.proofs


# Comandi: un errore di battitura non deve costare un'esplorazione


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
    monkeypatch.setattr("agency.runtime.open_session", lambda _: session)
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
    monkeypatch.setattr("agency.runtime.open_session", lambda _: session)
    assert cli.main(["run", "officina", "brief.md", "--budget", "30"]) == 1
    assert "esiste già" in capsys.readouterr().out


def test_run_does_not_start_without_a_declared_budget(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Il tetto lo dichiara chi avvia (ADR-0043): un valore dell'ambiente non è una scelta del cliente."""
    monkeypatch.setenv("AGENCY_PROJECT_BUDGET_USD", "40")
    opened: list[object] = []
    monkeypatch.setattr("agency.runtime.open_session", lambda settings: opened.append(settings))
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
    monkeypatch.setattr("agency.runtime.open_session", lambda _: pytest.fail("non doveva partire"))
    with pytest.raises(SystemExit) as stopped:
        cli.main([*command, amount])
    assert stopped.value.code == 2
    assert "importo positivo in dollari" in capsys.readouterr().err


def test_settings_have_no_budget_of_their_own() -> None:
    """Prima c'era AGENCY_PROJECT_BUDGET_USD: 25 $ nel codice, 40 $ nell'ambiente, 30 $ nella roadmap."""
    assert not any("budget" in name for name in Settings.model_fields)


def test_budget_of_an_unknown_project_is_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
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
    from agency.runtime import open_session

    transport = ScriptedTransport(responses)
    monkeypatch.setattr("agency.runtime.open_session", lambda settings: open_session(settings, transport))
    return transport


BLOCK_AT_ONCE = {
    "content": [{"type": "tool_use", "id": "t1", "name": "block", "input": {"reason": "prova del tetto"}}],
    "stop_reason": "tool_use",
    "model": "claude-sonnet-5-5",
    "usage": {"input_tokens": 100, "output_tokens": 20},
}


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


def test_a_brief_that_is_not_utf8_leaves_the_project_name_stuck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Pins current behavior of COR-004; phase 2 (Task 2.10) flips these assertions.
    path = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_bytes("Un segno per il caffè".encode("cp1252"))
    scripted_run(monkeypatch, [])
    with pytest.raises(UnicodeDecodeError):
        cli.main(["run", "forno", str(brief), "--budget", "5"])
    assert Ledger(path).project("forno") is not None  # saved before the brief was read
    capsys.readouterr()
    assert cli.main(["run", "forno", str(brief), "--budget", "5"]) == 1
    assert "esiste già" in capsys.readouterr().out


def test_network_failure_keeps_the_work_and_says_how_to_resume(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def fail() -> None:
        raise anthropic.APIConnectionError(request=request)

    assert cli._guarded("officina", session, fail) == 3  # type: ignore[attr-defined]
    assert "agency resume officina" in capsys.readouterr().out


def test_blocked_outcome_is_shown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = FakeSession([], Ledger(tmp_path / "l.sqlite"))
    monkeypatch.setattr(cli, "_show", lambda *_: 0)
    cli._guarded("officina", session, lambda: "bloccato: manca il brief")  # type: ignore[attr-defined]
    assert "manca il brief" in capsys.readouterr().out


# Contratti di revisione: su merlo3 quattro revisori hanno finito il lavoro senza poterlo consegnare


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
    """Il primo tentativo del direttore, su merlo3: il messaggio lo portava fuori strada."""
    result = open_review(studio(tmp_path), outputs=["reviews/critica.md"], checks={"*.svg": ["critique"]})
    assert result.get("is_error")
    assert "exports/segno.svg" in result["content"]
    assert "reviews/critica.md" in result["content"]


def test_a_visual_check_needs_something_that_can_be_rendered() -> None:
    with pytest.raises(delivery.ContractRefused, match="render"):
        delivery.validate(spec(checks={"*.md": ["visual_review"]}))


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
    """Su merlo3 il critico ha rifatto svg_audit dopo il QA: il direttore non poteva più accettare il QA."""
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
