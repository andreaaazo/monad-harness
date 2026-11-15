"""Defects found by rereading the system before M2: the review contracts, which four reviewers on merlo3 could
not deliver."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agency.contracts.project import ProjectName
from agency.contracts.ticket import TicketType
from agency.entrypoints import cli
from agency.ledger import Ledger
from agency.qa import delivery, evidence
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from support.hardening import (
    BLOCK_AT_ONCE,
    busy_line,
    call,
    cli_data,
    context,
    hold_project_lock,
    needs_craft,
    scripted_run,
    spec,
)
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)
from support.rules import RULES
from support.settings import settings

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
        rules=RULES,
    )


def proof(reviewer: ToolContext, check: str, result: str = "PASS") -> None:
    file = "exports/segno.svg"
    evidence.record(
        reviewer.ledger,
        reviewer.work,
        "p",
        file,
        check,
        result,
        reviewer.actor,
        reviewer.ticket_id,
        "x.png",
        rules=RULES,
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
        delivery.validate(spec(checks={"*.md": [check]}), rules=RULES)


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
