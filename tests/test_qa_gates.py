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

from agency.agents.toolbox import Toolbox, role_tools
from agency.artifacts import FileStore
from agency.config import REPO_ROOT
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType, Verdict
from agency.ledger import Ledger
from agency.ledger.models import DerivationRow
from agency.ledger.store import now
from agency.qa import checks, delivery, evidence
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.files import OutsidePerimeter, sha256
from agency.workshop.sandbox import Completed, Sandbox
from support.rules import RULES

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


def test_a_measurement_is_stored_as_measured_and_passes_as_measured(tmp_path: Path) -> None:
    """A measure check reports a value, not a verdict: its PASS is stored as MEASURED, which lets the file
    pass."""
    studio = Studio(tmp_path)
    ticket_id, _ = studio.open()
    studio.sign("diversity", "PASS", "qa-inspector", ticket_id)
    assert [(row.check_name, row.result) for row in studio.ledger.evidence("p")] == [
        ("diversity", "MEASURED")
    ]
    assert evidence.accepted("diversity", rules=RULES) == ("PASS", "NOT_APPLICABLE", "MEASURED")
    assert evidence.accepted("critique", rules=RULES) == ("PASS", "NOT_APPLICABLE")


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
            self.ledger,
            self.work,
            "p",
            file,
            check,
            result,
            actor,
            ticket_id,
            "proof.png",
            inputs=inputs,
            rules=RULES,
        )

    def deliver(self, ticket_id: str, actor: str, verdict: Verdict | None = None) -> None:
        hashes = {FILE: sha256(self.work / FILE)}
        self.ledger.apply(ticket_id, Action.DELIVER, actor, "consegna", verdict, hashes)

    def problems(
        self, spec: TicketSpec, verdict: Verdict | None = None, inputs: dict[str, str] | None = None
    ) -> list[str]:
        return delivery.delivery_problems(
            self.ledger, "p", self.sandbox, spec, verdict, inputs=inputs, rules=RULES
        )[1]

    def acceptance(self, ticket_id: str) -> list[str]:
        return delivery.acceptance_problems(self.ledger, "p", self.sandbox, ticket_id, rules=RULES)

    def context(self, actor: str, ticket_id: str) -> ToolContext:
        instance = f"{ticket_id}-i"
        index = CommandIndex([])
        return ToolContext(
            actor, "p", ticket_id, instance, self.ledger, self.sandbox, index, self.artifacts, rules=RULES
        )


# Delivery stops on a failed check and on stale proofs (TST-001, TST-003)


def test_a_failed_svg_audit_refuses_delivery(tmp_path: Path) -> None:
    """The real check runs in the sandbox: a broken SVG fails, and the failure blocks the delivery."""
    studio = Studio(tmp_path)
    (studio.work / FILE).write_text("<svg")
    ticket_id, spec = studio.open()
    author = "identity-designer"
    outcome = checks.run(
        studio.sandbox, studio.ledger, "p", ticket_id, author, "svg_audit", FILE, rules=RULES
    )
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
        delivery.validate(ticket(checks={"*.svg": ["svg-audit"]}), rules=RULES)


def test_an_output_without_a_check_is_refused_at_opening() -> None:
    refusal = re.escape("output senza controllo: exports/extra.png")
    with pytest.raises(delivery.ContractRefused, match=refusal):
        delivery.validate(ticket(outputs=[FILE, "exports/extra.png"]), rules=RULES)


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
    result = Toolbox(director, role_tools(RULES, "design-director")).call(
        "t1", "accept_ticket", {"ticket": child}
    )
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


# The QA modules list, hash and name files without following links (Tasks 2.F17, 2.F18, 2.F27)


def plant_host(tmp_path: Path) -> Path:
    """A folder outside the work folder, with files whose names must never reach a message."""
    host = tmp_path / "host"
    host.mkdir()
    (host / "riservato.svg").write_text(SVG)
    return host


def host_state(host: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in host.iterdir()}


def link_exports_to(studio: Studio, host: Path) -> None:
    shutil.rmtree(studio.work / "exports")
    (studio.work / "exports").symlink_to(host, target_is_directory=True)


def test_a_glob_output_through_a_linked_folder_matches_nothing(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    link_exports_to(studio, host)
    spec = ticket(outputs=["exports/*.svg"])
    assert delivery.expected(spec, studio.work) == ([], ["exports/*.svg"])
    _, problems = delivery.delivery_problems(studio.ledger, "p", studio.sandbox, spec, None, rules=RULES)
    assert problems == ["exports/*.svg: nessun file corrisponde"]
    assert host_state(host) == {"riservato.svg": SVG.encode()}


def test_a_review_of_a_linked_folder_is_refused_without_its_names(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    spec = ticket(**(REVIEW | {"outputs": ["exports/*.svg", "reviews/critica.md"]}))
    delivery.validate_review(spec, studio.work, set(), rules=RULES)  # the folder is real: the review may open
    link_exports_to(studio, host)
    with pytest.raises(delivery.ContractRefused) as refused:
        delivery.validate_review(spec, studio.work, set(), rules=RULES)
    assert "exports/*.svg" in str(refused.value)
    assert "riservato" not in str(refused.value)


def test_expected_lists_the_real_files_of_a_glob_output_in_order(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    (studio.work / "exports/altro.svg").write_text(SVG)
    (studio.work / "exports/sotto").mkdir()
    (studio.work / "exports/sotto/z.svg").write_text(SVG)
    spec = ticket(outputs=["exports/**/*.svg", "reviews/*.md", "nulla/*"])
    assert delivery.expected(spec, studio.work) == (
        ["exports/altro.svg", "exports/segno.svg", "exports/sotto/z.svg", "reviews/critica.md"],
        ["nulla/*"],
    )


def test_a_delivered_file_that_became_a_link_is_missing(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    (studio.work / FILE).unlink()
    (studio.work / FILE).symlink_to(host / "riservato.svg")
    _, spec = studio.open()
    assert studio.problems(spec) == [f"{FILE}: output mancante"]
    assert host_state(host) == {"riservato.svg": SVG.encode()}


def test_a_changed_input_that_became_a_link_is_superseded(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    (studio.work / "brief.md").write_text("il brief")
    ticket_id, spec = studio.open(inputs=["brief.md"])
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    opened = {"brief.md": sha256(studio.work / "brief.md")}
    (studio.work / "brief.md").unlink()
    (studio.work / "brief.md").symlink_to(host / "riservato.svg")
    assert studio.problems(spec, inputs=opened) == ["input superato: brief.md è cambiato dopo l'apertura"]


def test_a_proof_is_refused_for_a_file_that_is_a_link(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    ticket_id, _ = studio.open()
    (studio.work / FILE).unlink()
    (studio.work / FILE).symlink_to(host / "riservato.svg")
    with pytest.raises(evidence.EvidenceRefused, match=f"file inesistente: {FILE}"):
        studio.sign("svg_audit", "PASS", "identity-designer", ticket_id)
    assert studio.ledger.evidence("p") == []


def test_a_proof_whose_file_or_input_became_a_link_is_missing_or_stale(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    host = plant_host(tmp_path)
    (studio.work / "source").mkdir()
    (studio.work / "source/precedente.md").write_text("v0")
    ticket_id, _ = studio.open()
    studio.sign("svg_audit", "PASS", "identity-designer", ticket_id, inputs=["source/precedente.md"])
    row = evidence.latest(studio.ledger, "p")[(FILE, "svg_audit")]
    assert evidence.freshness(row, studio.work) == "fresh"
    (studio.work / "source/precedente.md").unlink()
    (studio.work / "source/precedente.md").symlink_to(host / "riservato.svg")
    assert evidence.freshness(row, studio.work) == "STALE"
    (studio.work / FILE).unlink()
    (studio.work / FILE).symlink_to(host / "riservato.svg")
    assert evidence.freshness(row, studio.work) == "MISSING"


class ProofSandbox(Sandbox):
    """Plays the QA scripts: `optical_check` writes its `--out` image, `logo_proof` writes pngs into it."""

    def __init__(self, work: Path) -> None:
        super().__init__(work)
        self.outs: list[str] = []

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        out = command[command.index("--out") + 1]
        self.outs.append(out)
        destination = self.work / Path(out).relative_to("/job")
        source = command[command.index("--out") - 1]
        if command[1].endswith("optical_check.py"):
            destination.write_text(f"misura di {source}")
        else:
            for name in ("nero.png", "bianco.png"):
                (destination / name).write_text(f"{name} di {source}")
        return Completed(0, "ok", "")


def proof_studio(tmp_path: Path, *files: str) -> tuple[Studio, ProofSandbox]:
    studio = Studio(tmp_path)
    for file in files:
        (studio.work / file).parent.mkdir(parents=True, exist_ok=True)
        (studio.work / file).write_text(SVG)
    return studio, ProofSandbox(studio.work)


SAME_STEM = ["a/mark.svg", "b/mark.svg", "mark.svg", "mark.png"]


def test_optical_proofs_of_files_with_one_stem_are_distinct(tmp_path: Path) -> None:
    studio, sandbox = proof_studio(tmp_path, *SAME_STEM)
    proofs = [checks.execute(sandbox, "optical_check", file).proofs for file in SAME_STEM]
    assert proofs == [
        ("proofs/optical/a_mark.svg.png",),
        ("proofs/optical/b_mark.svg.png",),
        ("proofs/optical/mark.svg.png",),
        ("proofs/optical/mark.png.png",),
    ]
    for file, (proof,) in zip(SAME_STEM, proofs, strict=True):
        assert (studio.work / proof).read_text() == f"misura di /job/{file}"
    assert sandbox.outs == [f"/job/{proof}" for (proof,) in proofs]


def test_logo_proofs_of_files_with_one_stem_are_distinct(tmp_path: Path) -> None:
    studio, sandbox = proof_studio(tmp_path, *SAME_STEM)
    found = [checks.execute(sandbox, "logo_proof", file).proofs for file in SAME_STEM]
    folders = [
        "proofs/logo/a_mark.svg",
        "proofs/logo/b_mark.svg",
        "proofs/logo/mark.svg",
        "proofs/logo/mark.png",
    ]
    assert found == [(f"{folder}/bianco.png", f"{folder}/nero.png") for folder in folders]
    for file, folder in zip(SAME_STEM, folders, strict=True):
        assert (studio.work / folder / "nero.png").read_text() == f"nero.png di /job/{file}"


def test_a_proof_name_with_wildcard_characters_lists_only_its_own_folder(tmp_path: Path) -> None:
    _, sandbox = proof_studio(tmp_path, "[a]/m*rk.svg", "a/mark.svg")
    first = checks.execute(sandbox, "logo_proof", "[a]/m*rk.svg").proofs
    second = checks.execute(sandbox, "logo_proof", "a/mark.svg").proofs
    assert first == ("proofs/logo/[a]_m*rk.svg/bianco.png", "proofs/logo/[a]_m*rk.svg/nero.png")
    assert second == ("proofs/logo/a_mark.svg/bianco.png", "proofs/logo/a_mark.svg/nero.png")


def test_a_linked_proof_folder_is_not_created_into_or_listed(tmp_path: Path) -> None:
    """`proofs` is a link that stays inside the work folder: `inside()` lets it by, the helper refuses it."""
    studio, sandbox = proof_studio(tmp_path, FILE)
    (studio.work / "altrove").mkdir()
    (studio.work / "proofs").symlink_to(studio.work / "altrove", target_is_directory=True)
    for check in ("optical_check", "logo_proof"):
        with pytest.raises(OutsidePerimeter):
            checks.execute(sandbox, check, FILE)
    assert list((studio.work / "altrove").iterdir()) == []
    assert sandbox.outs == []


def test_logo_proofs_list_regular_files_only(tmp_path: Path) -> None:
    studio, _ = proof_studio(tmp_path, FILE)
    host = plant_host(tmp_path)

    class Planting(ProofSandbox):
        def run(self, command: list[str], timeout: float = 120) -> Completed:
            done = super().run(command, timeout)
            out = self.work / Path(command[command.index("--out") + 1]).relative_to("/job")
            (out / "furto.png").symlink_to(host / "riservato.svg")
            return done

    found = checks.execute(Planting(studio.work), "logo_proof", FILE).proofs
    assert found == ("proofs/logo/exports_segno.svg/bianco.png", "proofs/logo/exports_segno.svg/nero.png")
    assert host_state(host) == {"riservato.svg": SVG.encode()}


def test_the_render_hash_of_a_proof_never_follows_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file is swapped for a link after the existence check: the hash refuses it instead of reading it."""
    studio, sandbox = proof_studio(tmp_path)
    host = plant_host(tmp_path)
    (studio.work / FILE).unlink()
    (studio.work / FILE).symlink_to(host / "riservato.svg")
    monkeypatch.setattr(checks, "is_file_under", lambda root, relative: True)
    ticket_id, _ = studio.open()
    with pytest.raises(OutsidePerimeter):
        checks.run(
            sandbox, studio.ledger, "p", ticket_id, "identity-designer", "optical_check", FILE, rules=RULES
        )
    assert studio.ledger.evidence("p") == []


def test_a_check_is_refused_for_a_file_that_is_a_link_inside_the_work_folder(tmp_path: Path) -> None:
    """`inside()` lets a link that stays in the work folder by: the check must not even start on it."""
    studio, sandbox = proof_studio(tmp_path, "exports/vero.svg")
    ticket_id, _ = studio.open()
    (studio.work / "exports/via.svg").symlink_to(studio.work / "exports/vero.svg")
    with pytest.raises(evidence.EvidenceRefused, match=re.escape("file inesistente: exports/via.svg")):
        checks.run(
            sandbox,
            studio.ledger,
            "p",
            ticket_id,
            "identity-designer",
            "optical_check",
            "exports/via.svg",
            rules=RULES,
        )
    assert sandbox.outs == []


def test_an_export_that_is_a_link_is_not_checked_for_its_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Studio(tmp_path)
    (studio.work / "source").mkdir()
    (studio.work / MASTER).write_text("master")
    spec = ticket(
        outputs=[MASTER, FILE],
        checks={"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
        medium_why=None,
    )
    asked: list[str] = []

    def derivation(sandbox: Sandbox, ledger: Ledger, project: str, file: str, masters: list[str]) -> str:
        asked.append(file)
        return "senza master"

    monkeypatch.setattr(delivery.master, "problem", lambda sandbox, file: None)
    monkeypatch.setattr(delivery.master, "derivation_problem", derivation)
    problems = delivery.master_problems(studio.ledger, "p", studio.sandbox, spec, [MASTER, FILE])
    assert (problems, asked) == ([f"{FILE}: senza master"], [FILE])
    (studio.work / FILE).unlink()
    (studio.work / FILE).symlink_to(studio.work / MASTER)
    asked.clear()
    assert delivery.master_problems(studio.ledger, "p", studio.sandbox, spec, [MASTER, FILE]) == []
    assert asked == []


# --- The QA scripts mount (STR-004): qa owns it, and only a check adds it (ADR-0057) ---


def test_a_plain_sandbox_does_not_mount_the_qa_scripts(tmp_path: Path) -> None:
    assert checks.QA_MOUNT not in Sandbox(tmp_path).argv(["true"])


def test_a_check_mounts_the_qa_scripts_and_keeps_everything_else(tmp_path: Path) -> None:
    """The copy keeps the work folder, the toolchain, the read-only folders and /ops. The toolchain must
    exist: argv binds it only then, and python() falls back to python3 without it."""
    ops, toolchain = tmp_path / "ops", tmp_path / "t"
    (toolchain / "venv/bin").mkdir(parents=True)
    (toolchain / "venv/bin/python").touch()
    sandbox = Sandbox(tmp_path / "w", toolchain=toolchain, read_only=(tmp_path,), ops=ops)
    plain = sandbox.argv(["true"])
    copy = sandbox.with_mount(checks.SCRIPTS, checks.QA_MOUNT)
    mounted = copy.argv(["true"])
    at = mounted.index(checks.QA_MOUNT)
    assert mounted[at - 2 : at + 1] == ["--ro-bind", str(checks.SCRIPTS), checks.QA_MOUNT]
    assert mounted[: at - 2] + mounted[at + 1 :] == plain
    bound = plain.index(str(toolchain))
    assert plain[bound - 1 : bound + 2] == ["--ro-bind", str(toolchain), str(toolchain)]
    assert copy.python() == sandbox.python() == str(toolchain / "venv/bin/python")
    assert sandbox.argv(["true"]) == plain  # the original gains no mount


def test_the_qa_scripts_are_the_frozen_folder() -> None:
    assert checks.SCRIPTS == REPO_ROOT / "src/agency/qa/scripts"
