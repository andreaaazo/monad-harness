"""Prove legate alla versione di un file. La firma è sempre l'attore reale dell'harness."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from agency.config import REPO_ROOT
from agency.contracts.ticket import AUTHOR_TYPES
from agency.ledger import Ledger
from agency.ledger.models import EvidenceRow
from agency.ledger.store import now
from agency.tools.files import inside, sha256_under

CHECKS: dict[str, dict] = json.loads((REPO_ROOT / "registry/checks.json").read_text(encoding="utf-8"))[
    "checks"
]
ROLES: dict[str, dict] = json.loads((REPO_ROOT / "registry/roles.json").read_text(encoding="utf-8"))["roles"]
MEASUREMENTS = {name for name, spec in CHECKS.items() if spec["kind"] == "measure"}


class EvidenceRefused(Exception):
    """La prova non si può registrare: motivo nel messaggio."""


def check_problem(name: str) -> str | None:
    if name in CHECKS or (name.startswith("req:") and len(name) > 4):
        return None
    return (
        f"controllo sconosciuto '{name}': usa un nome del registro o req:<nome> per un requisito del progetto"
    )


def is_independent(name: str) -> bool:
    return bool(CHECKS.get(name, {}).get("independent"))


def accepted(name: str) -> tuple[str, ...]:
    return ("PASS", "NOT_APPLICABLE", "MEASURED") if name in MEASUREMENTS else ("PASS", "NOT_APPLICABLE")


def authors(ledger: Ledger, project: str, file: str) -> set[str]:
    """Chi ha prodotto il file: i destinatari dei ticket di produzione che lo dichiarano."""
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
) -> EvidenceRow:
    guard(ledger, project, file, check, actor)
    target = inside(work, file)
    if not target.exists():
        raise EvidenceRefused(f"file inesistente: {file}")
    if CHECKS.get(check, {}).get("kind") == "measure" and result == "PASS":
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
    ledger.add_evidence(row)
    return row


def latest(ledger: Ledger, project: str, signer: str | None = None) -> dict[tuple[str, str], EvidenceRow]:
    """Esito per file e controllo: sulla stessa versione un FAIL resta finché lo cambia chi l'ha dato."""
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
    target = inside(work, row.file)
    if not target.exists():
        return "MISSING"
    if sha256_under(work, row.file) != row.sha256:
        return "STALE"
    for path, digest in json.loads(row.inputs_json).items():
        source = inside(work, path)
        if not source.exists() or sha256_under(work, path) != digest:
            return "STALE"
    return "fresh"
