"""Runnable checks: the system runs them, reads the result, and signs with the real actor."""

from __future__ import annotations

import glob
from collections.abc import Callable
from dataclasses import dataclass

from agency.contracts.files import ensure_dir_under, glob_under, is_file_under, sha256_under
from agency.ledger import Ledger
from agency.qa import evidence
from agency.tools import master
from agency.tools.files import clip
from agency.tools.render import _stem
from agency.tools.sandbox import JOB, QA_MOUNT, Sandbox

RUNNABLE = ("master_open", "svg_audit", "svg_parity", "logo_proof", "optical_check")


@dataclass(frozen=True)
class CheckOutcome:
    """A check's result, its detail, and the proof files it made. A `PROOF` result is not recorded: whoever
    looks at the proof signs the result."""

    result: str
    detail: str
    proofs: tuple[str, ...] = ()


def _script(sandbox: Sandbox, name: str, *args: str) -> tuple[int, str]:
    done = sandbox.run([sandbox.python(), f"{QA_MOUNT}/{name}.py", *args], timeout=180)
    return done.code, done.output


def execute(sandbox: Sandbox, check: str, file: str) -> CheckOutcome:
    """Runs one check on `file` in the sandbox, without recording anything."""
    target = f"{JOB}/{file}"
    if check == "master_open":
        why = master.problem(sandbox, file)
        return CheckOutcome("FAIL" if why else "PASS", why or "il master si apre e contiene lavoro")
    if check in ("svg_audit", "svg_parity"):
        code, output = _script(sandbox, check, target)
        return CheckOutcome("FAIL" if code else "PASS", clip(output, 1800))
    if check == "optical_check":
        proof = f"proofs/optical/{_stem(file)}.png"
        ensure_dir_under(sandbox.work, "proofs/optical")
        code, output = _script(sandbox, check, target, "--out", f"{JOB}/{proof}")
        if code:  # a measurement that failed is not a proof
            return CheckOutcome("FAIL", clip(output, 1800))
        # It is a measurement: it says what is there, not that it is right.
        return CheckOutcome("MEASURED", clip(output, 1800), (proof,))
    if check == "logo_proof":
        folder = f"proofs/logo/{_stem(file)}"
        ensure_dir_under(sandbox.work, folder)
        code, output = _script(sandbox, check, "proof", target, "--out", f"{JOB}/{folder}")
        if code:
            return CheckOutcome("FAIL", clip(output, 1800))
        found = glob_under(sandbox.work, f"{glob.escape(folder)}/*.png")
        # Whoever looks at the sheet decides the result: this only produces the proof.
        return CheckOutcome("PROOF", clip(output, 800), tuple(found))
    raise ValueError(f"controllo non eseguibile: {check}")


def run(
    sandbox: Sandbox,
    ledger: Ledger,
    project: str,
    ticket_id: str,
    actor: str,
    check: str,
    file: str,
    resume: Callable[[CheckOutcome], tuple[str, str, str, str]] | None = None,
) -> CheckOutcome:
    """Runs a runnable check and records its proof, signed by `actor`.

    `resume` makes the tool call's resume record from the outcome; it is written with the evidence row.
    """
    if check not in RUNNABLE:
        raise evidence.EvidenceRefused(f"{check} non si esegue: usa observe, judge o record_requirement")
    evidence.guard(ledger, project, file, check, actor)
    if not is_file_under(sandbox.work, file):
        raise evidence.EvidenceRefused(f"file inesistente: {file}")
    outcome = execute(sandbox, check, file)
    if outcome.proofs:
        ledger.add_render(project, file, sha256_under(sandbox.work, file), outcome.proofs)
    if outcome.result != "PROOF":
        evidence.record(
            ledger,
            sandbox.work,
            project,
            file,
            check,
            outcome.result,
            actor,
            ticket_id,
            proof=outcome.proofs[0] if outcome.proofs else "",
            note=outcome.detail[:400],
            operation=resume(outcome) if resume else None,
        )
    return outcome
