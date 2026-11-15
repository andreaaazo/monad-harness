"""Defects found by rereading the system before M2: the registry, the proofs and the Craft commands."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from agency.config import Settings
from agency.contracts.gate import ConceptGate
from agency.contracts.ledger import (
    EvidenceEntry,
    UsageEntry,
)
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import Action
from agency.entrypoints import cli
from agency.entrypoints.cli import render as report
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from agency.qa import checks as qa
from agency.workshop.sandbox import Sandbox
from support.hardening import BLOCK_AT_ONCE, FakeSession, cli_data, needs_craft, scripted_run, spec
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)
from support.scripted import ScriptedTransport
from support.settings import settings

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
                    EvidenceEntry(
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


def usage(ticket: str, step: int, at: str = "2026-11-01T00:00:00+00:00", instance: str = "i") -> UsageEntry:
    return UsageEntry(
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
