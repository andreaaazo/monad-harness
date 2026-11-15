"""Defects found by rereading the system before M2: the registry-wide claim, and the project paths the layout
takes."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency.config import Settings
from agency.contracts.layout import RelativeDataRoot
from agency.contracts.ledger import (
    ConceptEntry,
)
from agency.contracts.project import ProjectName, parse_project_name
from agency.entrypoints import cli
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop.craft import Command, CommandIndex
from support.concepts import open_idea
from support.hardening import (
    BLOCK_AT_ONCE,
    IdleSandbox,
    board_critic,
    busy_line,
    cli_data,
    context,
    hold_project_lock,
    rating,
    scripted_run,
    use,
)
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)
from support.settings import settings

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
        ConceptEntry(
            project=name, round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"
        ),
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
