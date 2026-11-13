"""Proofs bound to a version of a file. The signer is always the real actor the harness knows."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from agency.contracts.files import is_file_under, sha256_under
from agency.contracts.registry import CheckKind
from agency.contracts.ticket import AUTHOR_TYPES
from agency.ledger import Ledger
from agency.ledger.models import EvidenceRow
from agency.ledger.store import now
from agency.registry import CHECKS

MEASUREMENTS = {name for name, spec in CHECKS.items() if spec["kind"] == CheckKind.MEASURE}


class EvidenceRefused(Exception):
    """The proof cannot be recorded; the message says why."""


def check_problem(name: str) -> str | None:
    """Why `name` is not a check, or None for a registry check or a project requirement (`req:<name>`)."""
    if name in CHECKS or (name.startswith("req:") and len(name) > 4):
        return None
    return (
        f"controllo sconosciuto '{name}': usa un nome del registro o req:<nome> per un requisito del progetto"
    )


def is_independent(name: str) -> bool:
    """Whether the check must be signed by someone other than the file's author."""
    return bool(CHECKS.get(name, {}).get("independent"))


def accepted(name: str) -> tuple[str, ...]:
    """The results that let a file pass the check; a measurement also passes as MEASURED."""
    return ("PASS", "NOT_APPLICABLE", "MEASURED") if name in MEASUREMENTS else ("PASS", "NOT_APPLICABLE")


def authors(ledger: Ledger, project: str, file: str) -> set[str]:
    """Who made the file: the assignees of the authoring tickets that declare it or delivered it."""
    found = set()
    for row in ledger.tickets(project):
        spec = ledger.spec(row.id)
        if spec.type not in AUTHOR_TYPES:
            continue
        declared = [*spec.outputs, *json.loads(row.delivered_json)]
        if any(file == output or fnmatch.fnmatch(file, output) for output in declared):
            found.add(spec.assignee)
    return found


def guard(ledger: Ledger, project: str, file: str, check: str, actor: str) -> None:
    """Refuses an unknown check, and an independent one signed by the file's author or by a role it does not
    allow."""
    why = check_problem(check)
    if why:
        raise EvidenceRefused(why)
    spec = CHECKS.get(check, {})
    if spec.get("independent"):
        if actor in authors(ledger, project, file):
            raise EvidenceRefused(f"'{check}' è indipendente: {actor} è l'autore di {file}")
        if spec.get("roles") and actor not in spec["roles"]:
            raise EvidenceRefused(f"'{check}' lo firma {', '.join(spec['roles'])}, non {actor}")


def record(
    ledger: Ledger,
    work: Path,
    project: str,
    file: str,
    check: str,
    result: str,
    actor: str,
    ticket_id: str,
    proof: str = "",
    note: str = "",
    inputs: list[str] | None = None,
    operation: tuple[str, str, str, str] | None = None,
) -> EvidenceRow:
    """Records a proof on the file's current version, and on the current sha256 of each of `inputs`.

    `operation` is the resume record of the tool call behind this proof: it is written with the proof.
    """
    guard(ledger, project, file, check, actor)
    if not is_file_under(work, file):
        raise EvidenceRefused(f"file inesistente: {file}")
    if check in MEASUREMENTS and result == "PASS":
        result = "MEASURED"
    row = EvidenceRow(
        at=now(),
        project=project,
        file=file,
        sha256=sha256_under(work, file),
        check_name=check,
        result=result,
        signer=actor,
        ticket_id=ticket_id,
        proof=proof,
        note=note,
        inputs_json=json.dumps({path: sha256_under(work, path) for path in inputs or []}),
    )
    ledger.add_evidence(row, operation)
    return row


def latest(ledger: Ledger, project: str, signer: str | None = None) -> dict[tuple[str, str], EvidenceRow]:
    """The result per file and check: on the same version, a FAIL stands until its signer changes it."""
    versions: dict[tuple[str, str], tuple[str, dict[str, EvidenceRow]]] = {}
    for row in ledger.evidence(project):
        if signer and row.signer != signer:
            continue
        key = (row.file, row.check_name)
        sha, signers = versions.get(key, (row.sha256, {}))
        if sha != row.sha256:
            sha, signers = row.sha256, {}
        signers.pop(row.signer, None)
        signers[row.signer] = row
        versions[key] = (sha, signers)
    table = {}
    for key, (_, signers) in versions.items():
        ordered = list(signers.values())
        table[key] = next((row for row in reversed(ordered) if row.result == "FAIL"), ordered[-1])
    return table


def freshness(row: EvidenceRow, work: Path) -> str:
    """`fresh`; `STALE` if the file or one of its inputs changed or is gone; `MISSING` without the file."""
    if not is_file_under(work, row.file):
        return "MISSING"
    if sha256_under(work, row.file) != row.sha256:
        return "STALE"
    for path, digest in json.loads(row.inputs_json).items():
        if not is_file_under(work, path) or sha256_under(work, path) != digest:
            return "STALE"
    return "fresh"
