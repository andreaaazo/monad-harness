"""Characterization tests for the QA gates: delivery, acceptance and who may sign a proof.

They pin what `agency.qa.delivery` and `agency.qa.evidence` do today (docs/audit/PLAN.md, Phase 1,
Tasks 1.1-1.4). Each section names the audit findings whose missing coverage it closes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from agency.artifacts import FileStore
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType, Verdict
from agency.ledger import Ledger
from agency.ledger.models import DerivationRow
from agency.ledger.store import now
from agency.qa import checks, delivery, evidence
from agency.tools.craft import CommandIndex
from agency.tools.files import sha256
from agency.tools.sandbox import Sandbox
from agency.tools.surface import Toolbox, ToolContext, role_tools

needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="needs VectorCraft")

FILE = "exports/segno.svg"
MASTER = "source/segno.vectorcraft"
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<path d="M10 90 L50 10 L90 90 Z"/><path d="M20 20h10v10h-10z"/></svg>'
)
CRITIQUE_SIGNERS = "critic, art-director, creative-director, design-director, digital-director"
ROOT: dict[str, Any] = {
    "type": TicketType.DELIVERY,
    "sender": "router",
    "assignee": "design-director",
    "checks": {"*.svg": ["svg_audit", "critique"]},
    "media": [],
    "medium_why": None,
}
REVIEW: dict[str, Any] = {
    "type": TicketType.REVIEW,
    "assignee": "critic",
    "outputs": [FILE, "reviews/critica.md"],
    "checks": {"*.svg": ["critique"]},
    "media": [],
    "medium_why": None,
}


def ticket(**extra: Any) -> TicketSpec:
    """A production ticket for the identity designer: one SVG, checked by svg_audit, with no master."""
    values: dict[str, Any] = {
        "title": "Segno",
        "request": "Disegna il segno",
        "type": TicketType.PRODUCTION,
        "sender": "design-director",
        "assignee": "identity-designer",
        "outputs": [FILE],
        "checks": {"*.svg": ["svg_audit"]},
        "media": [Medium.NONE],
        "medium_why": "verifica del solo file, senza master",
    }
    return TicketSpec.model_validate(values | extra)


class Studio:
    """Project `p`: a work folder holding one valid SVG, a ledger and a sandbox, as the tools see them."""

    def __init__(self, root: Path) -> None:
        self.work = root / "work"
        (self.work / "exports").mkdir(parents=True)
        (self.work / "reviews").mkdir()
        (self.work / FILE).write_text(SVG)
        (self.work / "reviews/critica.md").write_text("referto")
        self.ledger = Ledger(root / "ledger.sqlite")
        self.sandbox = Sandbox(self.work)
        self.artifacts = FileStore(root / "artifacts")

    def open(self, **extra: Any) -> tuple[str, TicketSpec]:
        spec = ticket(**extra)
        return self.ledger.open(spec, "p"), spec

    def sign(
        self,
        check: str,
        result: str,
        actor: str,
        ticket_id: str,
        file: str = FILE,
        inputs: list[str] | None = None,
    ) -> None:
        evidence.record(
            self.ledger, self.work, "p", file, check, result, actor, ticket_id, "proof.png", inputs=inputs
        )

    def deliver(self, ticket_id: str, actor: str, verdict: Verdict | None = None) -> None:
        hashes = {FILE: sha256(self.work / FILE)}
        self.ledger.apply(ticket_id, Action.DELIVER, actor, "consegna", verdict, hashes)

    def problems(
        self, spec: TicketSpec, verdict: Verdict | None = None, inputs: dict[str, str] | None = None
    ) -> list[str]:
        return delivery.delivery_problems(self.ledger, "p", self.sandbox, spec, verdict, inputs=inputs)[1]

    def acceptance(self, ticket_id: str) -> list[str]:
        return delivery.acceptance_problems(self.ledger, "p", self.sandbox, ticket_id)

    def context(self, actor: str, ticket_id: str) -> ToolContext:
        instance = f"{ticket_id}-i"
        index = CommandIndex([])
        return ToolContext(actor, "p", ticket_id, instance, self.ledger, self.sandbox, index, self.artifacts)


# Delivery stops on a failed check and on stale proofs (TST-001, TST-003)


def test_a_failed_svg_audit_refuses_delivery(tmp_path: Path) -> None:
    """The real check runs in the sandbox: a broken SVG fails, and the failure blocks the delivery."""
    studio = Studio(tmp_path)
    (studio.work / FILE).write_text("<svg")
    ticket_id, spec = studio.open()
    author = "identity-designer"
    outcome = checks.run(studio.sandbox, studio.ledger, "p", ticket_id, author, "svg_audit", FILE)
    assert outcome.result == "FAIL"
    assert studio.problems(spec) == [f"{FILE}: 'svg_audit' è FAIL"]


def test_a_proof_of_an_older_version_is_stale(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    ticket_id, spec = studio.open()
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    assert studio.problems(spec) == []
    (studio.work / FILE).write_text(SVG.replace("M20 20", "M30 30"))
    assert studio.problems(spec) == [f"{FILE}: 'svg_audit' è STALE: il file è cambiato"]


def test_a_changed_comparison_file_makes_a_proof_stale(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "source").mkdir()
    (studio.work / "source/precedente.md").write_text("v0")
    ticket_id, spec = studio.open()
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id, inputs=["source/precedente.md"])
    assert studio.problems(spec) == []
    (studio.work / "source/precedente.md").write_text("v1")
    assert studio.problems(spec) == [f"{FILE}: 'svg_audit' è STALE: il file è cambiato"]


def test_an_input_changed_after_opening_supersedes_the_ticket(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "brief.md").write_text("il brief")
    ticket_id, spec = studio.open(inputs=["brief.md"])
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    opened = {"brief.md": sha256(studio.work / "brief.md")}
    assert studio.problems(spec, inputs=opened) == []
    (studio.work / "brief.md").write_text("un altro brief")
    assert studio.problems(spec, inputs=opened) == ["input superato: brief.md è cambiato dopo l'apertura"]


def test_a_vector_production_without_its_master_is_refused(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    ticket_id, spec = studio.open(media=[Medium.VECTOR], medium_why=None)
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    assert studio.problems(spec) == ["mezzo vettoriale: manca il master .vectorcraft (VectorCraft)"]


@needs_craft
def test_an_export_must_derive_from_the_current_master(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "source").mkdir()
    (studio.work / "source/disegno.svg").write_text(SVG)
    made = studio.sandbox.run(["vectorcraft-cli", "convert", "/job/source/disegno.svg", f"/job/{MASTER}"])
    assert made.code == 0, made.output
    ticket_id, spec = studio.open(
        outputs=[MASTER, FILE],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
        medium_why=None,
    )
    studio.sign("master_open", "PASS", "identity-designer", ticket_id, file=MASTER)
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    assert studio.problems(spec) == [f"{FILE}: non risulta esportato da un master del ticket"]

    def derived(master_sha: str) -> DerivationRow:
        return DerivationRow(
            at=now(),
            project="p",
            master=MASTER,
            master_sha=master_sha,
            export=FILE,
            export_sha=sha256(studio.work / FILE),
            how="test",
        )

    studio.ledger.add_derivation(derived("0" * 64))
    assert studio.problems(spec) == [f"{FILE}: il master è cambiato dopo l'export: riesporta"]
    studio.ledger.add_derivation(derived(sha256(studio.work / MASTER)))
    assert studio.problems(spec) == []


# The contract and verdict rules that keep a ticket deliverable (TST-011)


def test_an_unknown_check_name_is_refused_at_opening() -> None:
    with pytest.raises(delivery.ContractRefused, match="controllo sconosciuto 'svg-audit'"):
        delivery.validate(ticket(checks={"*.svg": ["svg-audit"]}))


def test_an_output_without_a_check_is_refused_at_opening() -> None:
    refusal = re.escape("output senza controllo: exports/extra.png")
    with pytest.raises(delivery.ContractRefused, match=refusal):
        delivery.validate(ticket(outputs=[FILE, "exports/extra.png"]))


def test_every_file_under_a_glob_output_needs_its_checks(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "exports/extra.png").write_bytes(b"png")
    ticket_id, spec = studio.open(outputs=["exports/*"])
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    assert studio.problems(spec) == ["exports/extra.png: nessun controllo lo copre"]


def test_a_review_delivered_not_verified_needs_no_proofs(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    _, spec = studio.open(**REVIEW)
    assert studio.problems(spec, Verdict.NOT_VERIFIED) == []
    assert studio.problems(spec, Verdict.READY) == [f"{FILE}: manca la prova 'critique'"]


def test_a_review_may_deliver_revise_on_a_fail(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    ticket_id, spec = studio.open(**REVIEW)
    studio.sign("critique", "FAIL", "critic", ticket_id)
    assert studio.problems(spec, Verdict.REVISE) == []
    assert studio.problems(spec, Verdict.READY) == [f"{FILE}: 'critique' è FAIL"]


# Acceptance adds the independent checks and the "unchanged since delivery" check (TST-002)


def test_acceptance_requires_the_independent_check(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, spec = studio.open(**ROOT)
    studio.sign("svg_audit", "PASS", "design-director", root)
    assert studio.problems(spec) == []  # delivery leaves independent checks to acceptance
    studio.deliver(root, "design-director")
    assert studio.acceptance(root) == [f"{FILE}: manca la prova 'critique'"]


def test_acceptance_refuses_an_independent_check_signed_by_the_assignee(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, _ = studio.open(**ROOT)
    studio.sign("svg_audit", "PASS", "design-director", root)
    studio.sign("critique", "PASS", "design-director", root)
    studio.deliver(root, "design-director")
    assert studio.acceptance(root) == [f"{FILE}: 'critique' è firmata dall'autore, serve un revisore"]


def test_acceptance_refuses_a_file_changed_after_delivery(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, _ = studio.open(**ROOT)
    studio.sign("svg_audit", "PASS", "design-director", root)
    studio.sign("critique", "PASS", "critic", root)
    studio.deliver(root, "design-director")
    assert studio.acceptance(root) == []
    (studio.work / FILE).write_text(SVG.replace("M20 20", "M30 30"))
    assert studio.acceptance(root)[0] == f"{FILE}: modificato dopo la consegna"


def test_accept_ticket_refuses_a_child_without_its_independent_check(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, _ = studio.open(**ROOT)
    child, _ = studio.open(checks={"*.svg": ["svg_audit", "critique"]}, parent=root)
    studio.sign("svg_audit", "PASS", "identity-designer", child)
    studio.deliver(child, "identity-designer")
    director = studio.context("design-director", root)
    result = Toolbox(director, role_tools("design-director")).call("t1", "accept_ticket", {"ticket": child})
    assert result.get("is_error"), result
    assert "accettazione rifiutata" in result["content"]
    assert f"{FILE}: manca la prova 'critique'" in result["content"]


# Who may sign a proof, and a FAIL persists (TST-004, TST-008; ADR-0018)


def test_a_reviewer_cannot_deliver_on_the_authors_proofs(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    production, _ = studio.open()
    studio.sign("svg_audit", "PASS", "identity-designer", production)
    (studio.work / "reviews/qa.md").write_text("referto")
    _, qa = studio.open(
        type=TicketType.QA,
        assignee="qa-inspector",
        outputs=[FILE, "reviews/qa.md"],
        media=[],
        medium_why=None,
    )
    assert studio.problems(qa, Verdict.READY) == [f"{FILE}: manca la prova 'svg_audit'"]


def test_a_fail_stays_until_its_signer_changes_it(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, _ = studio.open(**ROOT)
    studio.sign("svg_audit", "PASS", "design-director", root)
    studio.sign("critique", "FAIL", "critic", root)
    studio.sign("critique", "PASS", "creative-director", root)
    studio.deliver(root, "design-director")
    assert studio.acceptance(root) == [f"{FILE}: 'critique' è FAIL"]
    studio.sign("critique", "PASS", "critic", root)
    assert studio.acceptance(root) == []


def test_an_author_cannot_sign_an_independent_check(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "copy.md").write_text("il testo")
    ticket_id, _ = studio.open(assignee="copywriter", outputs=["copy.md"], checks={"*.md": ["copy_review"]})
    with pytest.raises(evidence.EvidenceRefused, match="'copy_review' è indipendente: copywriter è l'autore"):
        studio.sign("copy_review", "PASS", "copywriter", ticket_id, file="copy.md")


def test_only_the_listed_roles_sign_an_independent_check(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    root, _ = studio.open(**ROOT)
    refusal = f"'critique' lo firma {CRITIQUE_SIGNERS}, non qa-inspector"
    with pytest.raises(evidence.EvidenceRefused, match=refusal):
        studio.sign("critique", "PASS", "qa-inspector", root)
    studio.sign("critique", "PASS", "critic", root)
    assert [row.signer for row in studio.ledger.evidence("p")] == ["critic"]
