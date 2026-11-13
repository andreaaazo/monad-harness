"""Each run records its own fingerprint, and two runs say what changed (M1.6, item 4)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlmodel import Session

from agency import cli
from agency.config import REPO_ROOT, Settings
from agency.contracts.run import Change, Fingerprint, RunCommand, changes, read_fingerprint
from agency.ledger import Ledger
from agency.ledger.models import RunRow
from agency.telemetry import fingerprint

A, B, C, D, E = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)


def sample(**extra: object) -> Fingerprint:
    base: dict[str, object] = {
        "model": "",
        "effort": "",
        "explorer_effort": "high",
        "proposal_effort": "high",
        "explorers": 5,
        "max_parallel": 5,
        "prompts": {"prompts/common.md": A, "prompts/roles/explorer.md": B},
        "registry": {"registry/roles.json": C},
        "code": {"src/agency/cli.py": D},
        "lock": E,
        "python": "3.13.7",
        "tools": {"vectorcraft-cli": "vectorcraft-cli 0.18.0"},
    }
    return Fingerprint.model_validate(base | extra)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def plain() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


# The rules: pure, with no files or processes


def test_read_fingerprint_returns_none_for_what_it_cannot_read() -> None:
    assert read_fingerprint(sample().model_dump_json()) == sample()
    assert read_fingerprint('{"model": "", "effort": "", "explorer_effort": "high"}') is None
    assert read_fingerprint("{") is None


def test_identical_runs_have_no_changes_and_the_same_digest() -> None:
    assert changes(sample(), sample()) == []
    assert sample().digest() == sample().digest()


def test_digest_does_not_depend_on_the_order_of_the_files() -> None:
    one = sample(prompts={"prompts/common.md": A, "prompts/roles/explorer.md": B})
    other = sample(prompts={"prompts/roles/explorer.md": B, "prompts/common.md": A})
    assert one.digest() == other.digest()


def test_changed_prompt_is_named_with_both_hashes() -> None:
    after = sample(prompts={"prompts/common.md": A, "prompts/roles/explorer.md": "f" * 64})
    assert changes(sample(), after) == [
        Change(part="prompts", item="prompts/roles/explorer.md", before=B, after="f" * 64)
    ]
    assert after.digest() != sample().digest()


def test_added_and_removed_files_are_changes() -> None:
    after = sample(prompts={"prompts/common.md": A, "prompts/roles/nuovo.md": "1" * 64})
    assert changes(sample(), after) == [
        Change(part="prompts", item="prompts/roles/explorer.md", before=B, after=None),
        Change(part="prompts", item="prompts/roles/nuovo.md", before=None, after="1" * 64),
    ]


def test_changes_follow_the_order_of_the_fingerprint() -> None:
    after = sample(
        tools={"vectorcraft-cli": "vectorcraft-cli 0.18.1"},
        lock="0" * 64,
        effort="medium",
        model="claude-sonnet-5-5",
    )
    assert [(c.part, c.item, c.before, c.after) for c in changes(sample(), after)] == [
        ("model", "", "", "claude-sonnet-5-5"),
        ("effort", "", "", "medium"),
        ("lock", "", E, "0" * 64),
        ("tools", "vectorcraft-cli", "vectorcraft-cli 0.18.0", "vectorcraft-cli 0.18.1"),
    ]


OTHER: dict[str, object] = {
    "model": "claude-sonnet-5-5",
    "effort": "low",
    "explorer_effort": "medium",
    "proposal_effort": "medium",
    "explorers": 3,
    "max_parallel": 2,
    "prompts": {"prompts/common.md": "9" * 64, "prompts/roles/explorer.md": B},
    "registry": {"registry/roles.json": "9" * 64},
    "code": {"src/agency/cli.py": "9" * 64},
    "lock": "9" * 64,
    "python": "3.13.8",
    "tools": {"vectorcraft-cli": "vectorcraft-cli 0.19.0"},
}


def test_every_part_of_the_fingerprint_is_covered_by_this_test() -> None:
    assert set(OTHER) == set(Fingerprint.model_fields)


@pytest.mark.parametrize("part", sorted(OTHER))
def test_every_part_of_the_fingerprint_can_show_a_change(part: str) -> None:
    found = changes(sample(), sample(**{part: OTHER[part]}))
    assert [change.part for change in found] == [part]


# The fingerprint taken from the files and the CLIs


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    files = {
        "prompts/common.md": "comune",
        "prompts/roles/explorer.md": "esplora",
        "prompts/skills/critique/SKILL.md": "giudica",
        "registry/roles.json": "{}",
        "src/agency/cli.py": "codice",
        "src/agency/__pycache__/cli.cpython-313.pyc": "compilato",
        "uv.lock": "versioni",
    }
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_fingerprint_covers_prompts_registry_code_and_lock(tmp_path: Path) -> None:
    taken = fingerprint.take(plain(), "", "", root=repository(tmp_path), tools=())
    assert taken.prompts == {
        "prompts/common.md": sha("comune"),
        "prompts/roles/explorer.md": sha("esplora"),
        "prompts/skills/critique/SKILL.md": sha("giudica"),
    }
    assert taken.registry == {"registry/roles.json": sha("{}")}
    assert taken.code == {"src/agency/cli.py": sha("codice")}
    assert taken.lock == sha("versioni")


def test_fingerprint_keeps_the_choices_that_decide_model_and_effort(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, explorer_effort="medium", explorers=3, max_parallel=2)  # type: ignore[call-arg]
    taken = fingerprint.take(settings, "claude-sonnet-5-5", "low", root=repository(tmp_path), tools=())
    chosen = (taken.model, taken.effort, taken.explorer_effort, taken.proposal_effort)
    assert chosen == ("claude-sonnet-5-5", "low", "medium", "high")
    assert (taken.explorers, taken.max_parallel) == (3, 2)


def test_editing_a_prompt_shows_up_as_the_only_change(tmp_path: Path) -> None:
    root = repository(tmp_path)
    before = fingerprint.take(plain(), "", "", root=root, tools=())
    (root / "prompts/roles/explorer.md").write_text("esplora meglio", encoding="utf-8")
    after = fingerprint.take(plain(), "", "", root=root, tools=())
    assert [(c.part, c.item) for c in changes(before, after)] == [("prompts", "prompts/roles/explorer.md")]


def test_tool_versions_are_the_first_line_of_their_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    talks = bin_dir / "prova-versione-cli"
    talks.write_text("#!/bin/sh\necho 'prova 1.2.3'\necho 'build di oggi'\n", encoding="utf-8")
    silent = bin_dir / "prova-muta-cli"
    silent.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    broken = bin_dir / "prova-guasta-cli"
    broken.write_text("#!/bin/sh\necho 'Traceback'\nexit 1\n", encoding="utf-8")
    for script in (talks, silent, broken):
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    tools = ("prova-versione-cli", "prova-muta-cli", "prova-guasta-cli", "prova-assente-cli")
    taken = fingerprint.take(plain(), "", "", root=repository(tmp_path), tools=tools)
    assert taken.tools == {
        "prova-versione-cli": "prova 1.2.3",
        "prova-muta-cli": "non risponde",
        "prova-guasta-cli": "non risponde",
        "prova-assente-cli": "assente",
    }


def test_tools_never_see_the_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    spy = bin_dir / "prova-spia-cli"
    spy.write_text('#!/bin/sh\necho "chiave:${ANTHROPIC_API_KEY:-nessuna}"\n', encoding="utf-8")
    spy.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-prova")
    taken = fingerprint.take(plain(), "", "", root=repository(tmp_path), tools=("prova-spia-cli",))
    assert taken.tools == {"prova-spia-cli": "chiave:nessuna"}


def test_real_fingerprint_names_every_role_and_the_production_tools() -> None:
    taken = fingerprint.take(plain(), "", "")
    roles = {path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / "prompts/roles").glob("*.md")}
    assert len(roles) == 11 and roles <= set(taken.prompts)
    assert "src/agency/telemetry/fingerprint.py" in taken.code
    assert set(taken.tools) == {
        "vectorcraft-cli",
        "effectcraft-cli",
        "photocraft-cli",
        "figcraft-cli",
        "blender",
    }


# The registry


def test_runs_are_recorded_in_order_with_their_fingerprint(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    first = ledger.record_run("officina", RunCommand.RUN, sample())
    ledger.record_run("altro", RunCommand.RUN, sample())
    second = ledger.record_run("officina", RunCommand.DECIDE, sample(model="claude-sonnet-5-5"))

    rows = ledger.runs("officina")

    assert [(row.seq, row.project, row.command) for row in rows] == [
        (first, "officina", "run"),
        (second, "officina", "decide"),
    ]
    assert Fingerprint.model_validate_json(rows[1].fingerprint_json) == sample(model="claude-sonnet-5-5")
    assert rows[1].digest == sample(model="claude-sonnet-5-5").digest()
    found = ledger.run(second)
    assert found is not None and found.fingerprint_json == rows[1].fingerprint_json
    assert ledger.run(second + 100) is None


@pytest.mark.parametrize("statement", ["UPDATE runs SET command = 'resume'", "DELETE FROM runs"])
def test_runs_are_append_only(tmp_path: Path, statement: str) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_run("officina", RunCommand.RUN, sample())
    with ledger.engine.begin() as connection, pytest.raises(Exception, match="solo in aggiunta"):
        connection.exec_driver_sql(statement)


# The commands


@pytest.fixture
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path))
    return Ledger(tmp_path / "ledger.sqlite")


def test_runs_lists_executions_and_what_changed_from_the_one_before(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    changed = sample(prompts={"prompts/common.md": A, "prompts/roles/explorer.md": "f" * 64}, effort="low")
    data.record_run("officina", RunCommand.RUN, sample())
    data.record_run("officina", RunCommand.DECIDE, sample())
    data.record_run("officina", RunCommand.RESUME, changed)

    assert cli.main(["runs", "officina"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "officina: 3 esecuzioni"
    assert "run" in lines[1] and sample().digest()[:12] in lines[1]
    assert "decide" in lines[2] and "identica alla precedente" in lines[2]
    assert "resume" in lines[3] and changed.digest()[:12] in lines[3]
    assert "2 differenze dalla precedente: effort, prompts/roles/explorer.md" in lines[3]


def test_runs_counts_one_difference_and_names_at_most_five(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    many = sample(code={f"src/agency/m{n}.py": D for n in range(7)})
    data.record_run("officina", RunCommand.RUN, sample())
    data.record_run("officina", RunCommand.DECIDE, sample(effort="low"))
    data.record_run("officina", RunCommand.RESUME, many)

    assert cli.main(["runs", "officina"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[2].endswith("1 differenza dalla precedente: effort")
    names = ", ".join(["effort", "src/agency/cli.py"] + [f"src/agency/m{n}.py" for n in range(3)])
    assert lines[3].endswith(f"9 differenze dalla precedente: {names} e altre 4")


def test_runs_of_a_project_without_fingerprints_says_why(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["runs", "merlo3"]) == 0
    assert "precedenti a M1.6" in capsys.readouterr().out


def test_compare_shows_every_difference_between_two_executions(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    first = data.record_run("merlo4", RunCommand.RUN, sample())
    after = sample(
        model="claude-sonnet-5-5",
        prompts={"prompts/common.md": A},
        tools={"vectorcraft-cli": "vectorcraft-cli 0.18.1"},
    )
    second = data.record_run("merlo5", RunCommand.RUN, after)

    assert cli.main(["compare", str(first), str(second)]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"#{first} merlo4 run → #{second} merlo5 run: 3 differenze"
    assert lines[1:] == [
        "  model: predefinito → claude-sonnet-5-5",
        f"  prompts prompts/roles/explorer.md: {B[:12]} → assente",
        "  tools vectorcraft-cli: vectorcraft-cli 0.18.0 → vectorcraft-cli 0.18.1",
    ]


UNREADABLE = "impronta di una forma che questa versione non legge"


def record_unreadable(ledger: Ledger, project: str) -> int:
    """Store a fingerprint of an old shape, the way a registry written by an earlier version holds it."""
    old_shape = '{"model": "", "effort": "", "explorer_effort": "high"}'
    row = RunRow(
        at="2026-11-01T00:00:00+00:00",
        project=project,
        command="run",
        digest="0" * 64,
        fingerprint_json=old_shape,
    )
    with Session(ledger.engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.seq is not None
        return row.seq


def test_runs_lists_an_unreadable_fingerprint(data: Ledger, capsys: pytest.CaptureFixture[str]) -> None:
    data.record_run("officina", RunCommand.RUN, sample())
    record_unreadable(data, "officina")
    data.record_run("officina", RunCommand.RESUME, sample(effort="low"))

    assert cli.main(["runs", "officina"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "officina: 3 esecuzioni"
    assert lines[2].endswith(f"{'0' * 12}  {UNREADABLE}")
    assert lines[3].endswith("1 differenza dalla precedente: effort")


def test_compare_with_an_unreadable_fingerprint_says_it_cannot_compare(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    first = data.record_run("merlo4", RunCommand.RUN, sample())
    second = record_unreadable(data, "merlo4")

    assert cli.main(["compare", str(first), str(second)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"#{first} merlo4 run → #{second} merlo4 run: confronto non possibile",
        f"  #{second}: {UNREADABLE}",
    ]


def test_compare_of_identical_executions_says_so(data: Ledger, capsys: pytest.CaptureFixture[str]) -> None:
    first = data.record_run("merlo4", RunCommand.RUN, sample())
    second = data.record_run("merlo4", RunCommand.DECIDE, sample())
    assert cli.main(["compare", str(first), str(second)]) == 0
    assert capsys.readouterr().out.strip().endswith("nessuna differenza")


def test_compare_refuses_an_unknown_execution(data: Ledger, capsys: pytest.CaptureFixture[str]) -> None:
    first = data.record_run("merlo4", RunCommand.RUN, sample())
    assert cli.main(["compare", str(first), "999"]) == 1
    assert "#999" in capsys.readouterr().out


def test_resume_of_an_unknown_project_records_nothing(
    data: Ledger, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["resume", "fantasma"]) == 1
    assert "fantasma" in capsys.readouterr().out
    assert data.runs("fantasma") == []
