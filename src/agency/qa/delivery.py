"""Checks at delivery and at acceptance: the same logic for every ticket, with no exceptions."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from agency.contracts.files import glob_under, inside, is_file_under, sha256_under
from agency.contracts.ledger import LedgerPort
from agency.contracts.registry import CheckKind, StudioRules
from agency.contracts.ticket import (
    AUTHOR_TYPES,
    NO_CHECK_TYPES,
    REVIEW_TYPES,
    Medium,
    TicketSpec,
    Verdict,
)
from agency.qa import evidence
from agency.workshop import master, render
from agency.workshop.sandbox import Sandbox

GLOB = "*?["
REPORTS = "reviews/"
LOOKED_AT = (CheckKind.OBSERVATION, CheckKind.JUDGEMENT)  # recorded only by looking at a render of the file
REVIEW_SHAPE = (
    "Una revisione dichiara in outputs i file che giudica e il referto, con i controlli sui file giudicati: "
    'outputs ["exports/segno.svg", "reviews/critica.md"], checks {"*.svg": ["critique"]}.'
)


class ContractRefused(Exception):
    """The ticket is not a valid contract."""


def matches(file: str, pattern: str) -> bool:
    """Whether `pattern` matches the file's path, or its name alone."""
    return fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(Path(file).name, pattern)


def checks_for(spec: TicketSpec, file: str) -> list[str]:
    """The checks the contract asks for on `file`, from every pattern it matches, without duplicates."""
    found: list[str] = []
    for pattern, names in spec.checks.items():
        if matches(file, pattern):
            found += names
    return list(dict.fromkeys(found))


def exempted(spec: TicketSpec, file: str) -> bool:
    """Whether the contract exempts `file`, by its exact path or by a pattern."""
    return any(file == key or matches(file, key) for key in spec.exempt)


def _needs_coverage(spec: TicketSpec, file: str) -> bool:
    if spec.type in NO_CHECK_TYPES:
        return False
    return not (spec.type in REVIEW_TYPES and file.endswith(".md"))


def validate(spec: TicketSpec, rules: StudioRules) -> None:
    """Refuses, at opening, a contract that would let an output through unchecked."""
    for names in spec.checks.values():
        for name in names:
            why = evidence.check_problem(name, rules)
            if why:
                raise ContractRefused(why)
    for pattern in spec.checks:
        if not any(matches(output, pattern) or fnmatch.fnmatch(pattern, output) for output in spec.outputs):
            hint = f" {REVIEW_SHAPE}" if spec.type in REVIEW_TYPES else ""
            raise ContractRefused(
                f"il pattern '{pattern}' non corrisponde a nessun output: non controllerebbe nulla.{hint}"
            )
    for output in spec.outputs:
        unseen = [name for name in checks_for(spec, output) if _looked_at(name, rules)]
        if unseen and Path(output).suffix.lower() not in ("", *render.RENDERABLE):
            hint = f" {REVIEW_SHAPE}" if spec.type in REVIEW_TYPES else ""
            raise ContractRefused(
                f"{unseen} su {output}: nessuno può guardarlo, il render non esiste per questo file.{hint}"
            )
        if not _needs_coverage(spec, output) or exempted(spec, output) or checks_for(spec, output):
            continue
        if not any(fnmatch.fnmatch(pattern, output) for pattern in spec.checks):
            raise ContractRefused(
                f"output senza controllo: {output}. Aggiungilo in checks o in exempt con il motivo"
            )


def _looked_at(check: str, rules: StudioRules) -> bool:
    return rules.kind_of(check) in LOOKED_AT


def validate_review(spec: TicketSpec, work: Path, coming: set[str], rules: StudioRules) -> None:
    """A reviewer writes only in reviews/: any other contract would end in a report that cannot be delivered.

    `coming` are the files others are producing: a review can be opened before they exist.
    """
    if spec.assignee not in rules.reviewers():
        return
    absent = [
        output
        for output in spec.outputs
        if not output.startswith(REPORTS) and output not in coming and not glob_under(work, output)
    ]
    if absent:
        raise ContractRefused(
            f"un revisore non può produrre {absent}: scrive solo in {REPORTS}. {REVIEW_SHAPE}"
        )
    checked = [output for output in spec.outputs if output.startswith(REPORTS) and checks_for(spec, output)]
    if checked:
        raise ContractRefused(f"controlli sul referto {checked}: vanno sui file giudicati. {REVIEW_SHAPE}")


def expected(spec: TicketSpec, work: Path) -> tuple[list[str], list[str]]:
    """The output files a delivery must have, globs expanded, and the globs that matched nothing."""
    files: list[str] = []
    empty: list[str] = []
    for output in spec.outputs:
        if any(char in output for char in GLOB):
            found = glob_under(work, output)
            files += found
            if not found:
                empty.append(output)
        else:
            files.append(output)
    return list(dict.fromkeys(files)), empty


def coverage_problems(spec: TicketSpec, files: list[str]) -> list[str]:
    """One problem per file that needs a check and has neither a check nor an exemption."""
    return [
        f"{file}: nessun controllo lo copre"
        for file in files
        if _needs_coverage(spec, file) and not checks_for(spec, file) and not exempted(spec, file)
    ]


def evidence_problems(
    ledger: LedgerPort,
    project: str,
    work: Path,
    spec: TicketSpec,
    files: list[str],
    include_independent: bool,
    verdict: Verdict | None,
    rules: StudioRules,
) -> list[str]:
    """One problem per required proof that is missing, signed by the author when it must be independent,
    stale, or not passed. Outside reviews, independent checks count only at acceptance
    (`include_independent`). A review counts only its reviewer's proofs: NOT_VERIFIED asks for none, and
    REVISE does not ask them to pass."""
    review = spec.type in REVIEW_TYPES
    # A reviewer answers for their own proofs: another signer's neither replace nor cancel them.
    table = evidence.latest(ledger, project, spec.assignee if review else None)
    problems = []
    for file in files:
        for check in checks_for(spec, file):
            if review and verdict is Verdict.NOT_VERIFIED:
                continue
            independent = evidence.is_independent(check, rules)
            if independent and not include_independent and not review:
                continue
            row = table.get((file, check))
            if row is None:
                problems.append(f"{file}: manca la prova '{check}'")
            elif independent and not review and row.signer == spec.assignee:
                problems.append(f"{file}: '{check}' è firmata dall'autore, serve un revisore")
            elif evidence.freshness(row, work) != "fresh":
                problems.append(f"{file}: '{check}' è {evidence.freshness(row, work)}: il file è cambiato")
            elif not (review and verdict is Verdict.REVISE) and row.result not in evidence.accepted(
                check, rules
            ):
                problems.append(f"{file}: '{check}' è {row.result}")
    return problems


def master_problems(
    ledger: LedgerPort, project: str, sandbox: Sandbox, spec: TicketSpec, files: list[str]
) -> list[str]:
    """For an authoring ticket: each declared medium has its master, each master opens, and each export
    derives from a master unless `no_master` excuses it."""
    if spec.type not in AUTHOR_TYPES:
        return []  # a reviewer judges the work: the master is the author's job
    media = [medium for medium in spec.media if medium is not Medium.NONE]
    problems: list[str] = []
    masters: list[str] = []
    for medium in media:
        declared = master.MEDIA[medium]
        found = [file for file in files if file.lower().endswith(declared.master)]
        if not found:
            problems.append(f"mezzo {medium.value}: manca il master {declared.master} ({declared.tool})")
        masters += found
    for file in masters:
        why = master.problem(sandbox, file)
        if why:
            problems.append(f"{file}: {why}")
    extensions = tuple(extension for medium in media for extension in master.MEDIA[medium].exports)
    if not extensions or not masters:
        return problems
    for file in files:
        if not file.lower().endswith(extensions) or file.startswith("proofs/") or file in masters:
            continue
        if any(file == key or matches(file, key) for key in spec.no_master):
            continue
        if is_file_under(sandbox.work, file):
            why = master.derivation_problem(sandbox, ledger, project, file, masters)
            if why:
                problems.append(f"{file}: {why}")
    return problems


def delivery_problems(
    ledger: LedgerPort,
    project: str,
    sandbox: Sandbox,
    spec: TicketSpec,
    verdict: Verdict | None,
    inputs: dict[str, str] | None = None,
    *,
    rules: StudioRules,
) -> tuple[list[str], list[str]]:
    """The output files present, and what blocks the delivery: missing outputs, inputs changed since the
    opening, coverage, proofs and masters."""
    work = sandbox.work
    files, empty = expected(spec, work)
    stale = [
        f"input superato: {path} è cambiato dopo l'apertura"
        for path, digest in (inputs or {}).items()
        if not is_file_under(work, path) or sha256_under(work, path) != digest
    ]
    problems = [f"{pattern}: nessun file corrisponde" for pattern in empty]
    problems += [f"{file}: output mancante" for file in files if not is_file_under(work, file)]
    problems += stale
    present = [file for file in files if is_file_under(work, file)]
    problems += coverage_problems(spec, present)
    problems += evidence_problems(ledger, project, work, spec, present, False, verdict, rules)
    problems += master_problems(ledger, project, sandbox, spec, present)
    return present, problems


def acceptance_problems(
    ledger: LedgerPort, project: str, sandbox: Sandbox, ticket_id: str, rules: StudioRules
) -> list[str]:
    """What blocks acceptance: a delivered file changed since the delivery, or a required proof, independent
    ones included, that is not in order."""
    spec = ledger.spec(ticket_id)
    _, verdict = ledger.status(ticket_id)
    delivered = ledger.delivered(ticket_id)
    problems = [
        f"{file}: modificato dopo la consegna"
        for file, digest in delivered.items()
        if not inside(sandbox.work, file).exists() or sha256_under(sandbox.work, file) != digest
    ]
    problems += evidence_problems(ledger, project, sandbox.work, spec, list(delivered), True, verdict, rules)
    return problems
