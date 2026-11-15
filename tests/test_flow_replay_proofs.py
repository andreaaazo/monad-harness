"""Proofs on resume: a replayed requirement, observation, check, render or export adds nothing twice."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from agency.agents.toolbox import Toolbox
from agency.contracts.ledger import DerivationEntry, Tickets
from agency.ledger import Ledger
from agency.qa import checks
from agency.qa.checks import CheckOutcome
from agency.toolkit.base import ToolContext
from agency.workshop import master
from agency.workshop.files import sha256_under
from agency.workshop.sandbox import (
    Completed,
    Sandbox,
)
from support.flow import SEEN_RED, closing_box, crash_after_the_transition, intact, production_spec
from support.settings import settings


def resume_record_dies(
    box: Toolbox,
    context: ToolContext,
    monkeypatch: pytest.MonkeyPatch,
    tool_use_id: str,
    name: str,
    arguments: dict,
) -> bool:
    """Calls the tool while writing a resume record kills the process. True if the call was killed: a call
    whose effect and resume record are one transaction never reaches the separate write."""

    def die(*_: object) -> None:
        raise KeyboardInterrupt

    killed = False
    with monkeypatch.context() as patch:
        patch.setattr(context.ledger, "record_operation", die)
        try:
            box.call(tool_use_id, name, arguments)
        except KeyboardInterrupt:
            killed = True
    context.finished = None  # the process restarts: nothing of the old context survives
    return killed


def evidence_events(ledger: Tickets) -> int:
    return sum(event.action == "evidence" for row in ledger.tickets("p") for event in ledger.history(row.id))


def test_a_replayed_record_requirement_adds_one_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, context, _ = closing_box(tmp_path, production_spec(), "identity-designer", "record_requirement")
    (tmp_path / "work" / "nota.md").write_text("v1")
    arguments = {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}

    killed = resume_record_dies(box, context, monkeypatch, "t1", "record_requirement", arguments)
    result = box.call("t1", "record_requirement", arguments)

    assert len(context.ledger.evidence("p")) == 1
    assert evidence_events(context.ledger) == 1
    assert json.loads(result["content"]) == {"ok": True}
    assert context.ledger.operation("i:t1") == '{"ok": true}'
    assert [op.tool for op in context.ledger.operations("i")] == ["record_requirement"]
    assert not killed  # the proof and its resume record are one transaction: no window between them
    intact(context.ledger)


def test_a_replayed_observe_and_judge_add_one_proof_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, context, _ = closing_box(
        tmp_path, production_spec(), "critic", "render", "view_image", "observe", "judge"
    )
    work = tmp_path / "work"
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    Image.new("RGB", (100, 100), (30, 30, 200)).save(work / "b.png")
    (proof,) = json.loads(box.call("r1", "render", {"path": "a.png"})["content"])["proofs"]
    box.call("v1", "view_image", {"path": proof})
    observed = {"file": "a.png", "seen": SEEN_RED}
    why = "Il rosso pieno regge meglio del blu: bordi netti, contrasto alto, nessun elemento in più."
    judged = {"file": "a.png", "compare": ["b.png"], "why": why, "result": "PASS"}

    killed = [
        resume_record_dies(box, context, monkeypatch, "o1", "observe", observed),
        resume_record_dies(box, context, monkeypatch, "j1", "judge", judged),
    ]
    results = [box.call("o1", "observe", observed), box.call("j1", "judge", judged)]

    assert [row.check_name for row in context.ledger.evidence("p")] == ["visual_review", "critique"]
    assert evidence_events(context.ledger) == 2
    assert not any(result.get("is_error") for result in results), results
    assert json.loads(results[0]["content"]) == {
        "ok": True,
        "check": "visual_review",
        "result": "PASS",
        "proof": proof,
    }
    assert json.loads(results[1]["content"]) == {"ok": True, "check": "critique", "result": "PASS"}
    assert killed == [False, False]
    assert sorted(op.tool for op in context.ledger.operations("i") if op.id in ("i:o1", "i:j1")) == [
        "judge",
        "observe",
    ]
    intact(context.ledger)


def test_a_replayed_run_check_neither_reruns_nor_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, context, _ = closing_box(tmp_path, production_spec(), "identity-designer", "run_check")
    (tmp_path / "work" / "a.png").write_bytes(b"x")
    runs: list[str] = []

    def execute(sandbox: Sandbox, check: str, file: str) -> CheckOutcome:
        runs.append(check)
        return CheckOutcome("MEASURED", "misurato", ("proofs/optical/a.png",))

    monkeypatch.setattr(checks, "execute", execute)
    arguments = {"check": "optical_check", "file": "a.png"}

    killed = resume_record_dies(box, context, monkeypatch, "t1", "run_check", arguments)
    result = box.call("t1", "run_check", arguments)

    assert runs == ["optical_check"]  # the replay returned the recorded result
    assert json.loads(result["content"]) == {
        "result": "MEASURED",
        "detail": "misurato",
        "proofs": ["proofs/optical/a.png"],
    }
    assert len(context.ledger.evidence("p")) == 1
    assert evidence_events(context.ledger) == 1
    digest = sha256_under(tmp_path / "work", "a.png")
    assert context.ledger.renders_of("p", "a.png", digest) == ["proofs/optical/a.png"]
    assert not killed
    assert [op.tool for op in context.ledger.operations("i")] == ["run_check"]
    intact(context.ledger)


def test_a_run_check_that_makes_no_evidence_is_recorded_by_the_toolbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PROOF outcome writes no evidence row: the toolbox records the operation, as for any other effect."""
    box, context, _ = closing_box(tmp_path, production_spec(), "identity-designer", "run_check")
    (tmp_path / "work" / "a.png").write_bytes(b"x")
    monkeypatch.setattr(
        checks, "execute", lambda *_: CheckOutcome("PROOF", "fogli", ("proofs/logo/a/1.png",))
    )

    result = box.call("t1", "run_check", {"check": "logo_proof", "file": "a.png"})

    assert context.ledger.operation("i:t1") == result["content"]
    assert context.ledger.evidence("p") == []


def test_a_replayed_render_adds_no_second_render_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    box, context, _ = closing_box(tmp_path, production_spec(), "critic", "render")
    work = tmp_path / "work"
    Image.new("RGB", (100, 100), (200, 30, 30)).save(work / "a.png")
    arguments = {"path": "a.png", "zooms": [[0.1, 0.1, 0.5, 0.5]]}
    crash_after_the_transition(box, context, monkeypatch, "render", arguments)

    result = box.call("t1", "render", arguments)

    proofs = json.loads(result["content"])["proofs"]
    assert len(proofs) == 2
    assert sorted(context.ledger.renders_of("p", "a.png", sha256_under(work, "a.png"))) == sorted(proofs)


def test_add_render_keeps_a_new_source_version_and_a_new_proof(tmp_path: Path) -> None:
    ledger = Ledger(settings(tmp_path).layout.ledger)
    ledger.add_render("p", "a.png", "s1", ["x.png", "y.png"])
    ledger.add_render("p", "a.png", "s1", ["x.png", "y.png"])
    ledger.add_render("p", "a.png", "s2", ["x.png"])
    ledger.add_render("q", "a.png", "s1", ["x.png"])
    ledger.add_render("p", "b.png", "s1", ["x.png"])  # the same proof name for another source
    ledger.add_render("p", "a.png", "s1", ["z.png", "x.png"])  # only the new proof is added
    ledger.add_render("p", "d.png", "s1", ["w.png", "w.png"])  # one call, one proof twice
    assert ledger.renders_of("p", "d.png", "s1") == ["w.png"]

    assert ledger.renders_of("p", "a.png", "s1") == ["x.png", "y.png", "z.png"]
    assert ledger.renders_of("p", "a.png", "s2") == ["x.png"]
    assert ledger.renders_of("q", "a.png", "s1") == ["x.png"]
    assert ledger.renders_of("p", "b.png", "s1") == ["x.png"]


def derivation(**changes: str) -> DerivationEntry:
    fields: dict[str, Any] = {
        "at": "2026-01-01T00:00:00+00:00",
        "project": "p",
        "master": "m.vectorcraft",
        "master_sha": "m1",
        "export": "e.svg",
        "export_sha": "e1",
        "how": "vectorcraft-cli convert",
    }
    return DerivationEntry(**{**fields, **changes})


def test_add_derivation_skips_only_an_identical_row(tmp_path: Path) -> None:
    ledger = Ledger(settings(tmp_path).layout.ledger)
    ledger.add_derivation(derivation())
    ledger.add_derivation(derivation(at="2026-02-02T00:00:00+00:00"))  # same link, written again later
    assert len(ledger.derivations("p", "e.svg")) == 1
    for change in (
        {"master": "n.vectorcraft"},
        {"master_sha": "m2"},
        {"export_sha": "e2"},
        {"how": "altro"},
        {"project": "q"},
    ):
        before = len(ledger.derivations(change.get("project", "p"), "e.svg"))
        ledger.add_derivation(derivation(**change))
        assert len(ledger.derivations(change.get("project", "p"), "e.svg")) == before + 1, change
    ledger.add_derivation(derivation(export="f.svg"))
    assert len(ledger.derivations("p", "f.svg")) == 1


def test_a_replayed_export_master_adds_no_second_derivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, context, _ = closing_box(tmp_path, production_spec(), "identity-designer", "export_master")
    work = tmp_path / "work"
    (work / "source").mkdir()
    (work / "source" / "segno.vectorcraft").write_bytes(b"master")
    monkeypatch.setattr(master, "problem", lambda *_: None)

    def convert(command: list[str], **_: object) -> Completed:
        (work / "exports").mkdir(exist_ok=True)
        (work / "exports" / "segno.svg").write_bytes(b"<svg/>")
        return Completed(0, "", "")

    monkeypatch.setattr(context.sandbox, "run", convert)
    arguments = {"master": "source/segno.vectorcraft", "output": "exports/segno.svg"}
    crash_after_the_transition(box, context, monkeypatch, "export_master", arguments)
    assert len(context.ledger.derivations("p", "exports/segno.svg")) == 1

    result = box.call("t1", "export_master", arguments)

    assert not result.get("is_error"), result["content"]
    assert len(context.ledger.derivations("p", "exports/segno.svg")) == 1
