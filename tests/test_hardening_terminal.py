"""Defects found by rereading the system before M2: model text and outside text reach the terminal safely."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import anthropic
import httpx2
import pytest

from agency.contracts.gate import ConceptGate
from agency.contracts.ledger import (
    ArtifactEntry,
    JudgmentEntry,
    RunEntry,
)
from agency.contracts.project import ProjectName, parse_project_name
from agency.contracts.run import Fingerprint
from agency.entrypoints import cli
from agency.entrypoints.cli import render as report
from agency.evaluation.blind import CannotCompare
from agency.insights.domain import Provenance
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from support.hardening import FakeSession, cli_data, spec
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)

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


def _run_row(seq: int, command: str) -> RunEntry:
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
    return RunEntry(
        seq=seq,
        at="2026-11-01",
        project="p",
        command=command,
        digest="d" * 64,
        fingerprint_json=fingerprint.model_dump_json(),
    )


def _artifact_row(path: str) -> ArtifactEntry:
    return ArtifactEntry(
        at="2026-11-01",
        sha256="a" * 64,
        project="p",
        path=path,
        ticket_id="T-1",
        origin="consegna",
        media_type="text/plain",
        size=3,
    )


def _judgment_row(file: str) -> JudgmentEntry:
    return JudgmentEntry(
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
    def runs(self, _: str) -> list[RunEntry]:
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
