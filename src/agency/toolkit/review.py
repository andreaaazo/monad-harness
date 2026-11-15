"""The agent tools that verify: checks run by the system, observations, judgments and requirements."""

from __future__ import annotations

import os

from pydantic import Field

from agency import registry
from agency.contracts.registry import CheckKind
from agency.qa import checks as qa
from agency.qa import evidence
from agency.toolkit.base import Refused, Strict, Tool, ToolContext, result_text, viewed
from agency.workshop.files import is_file_under, sha256_under


class RunCheck(Strict):
    check: str
    file: str


class Observe(Strict):
    file: str
    seen: str = Field(description="Cosa hai visto: composizione, bordi, difetti. Almeno una frase concreta.")
    check: str = "visual_review"
    result: str = Field(default="PASS", pattern="^(PASS|FAIL)$")


class Judge(Strict):
    file: str
    compare: list[str] = Field(min_length=1, description="Alternativa, versione precedente o riferimento")
    why: str
    check: str = "critique"
    result: str = Field(pattern="^(PASS|FAIL)$")


class RecordRequirement(Strict):
    file: str
    check: str = Field(description="req:<nome> per un requisito del progetto")
    result: str = Field(pattern="^(PASS|FAIL|NOT_APPLICABLE)$")
    note: str


def _recorded(ctx: ToolContext, operation_id: str, name: str, value: dict) -> tuple[str, str, str, str]:
    """The resume record of a call whose result is `value`, to be written in the transaction of its proof."""
    return (operation_id, ctx.instance, name, result_text(value))


def _check_result(outcome: qa.CheckOutcome) -> dict:
    return {"result": outcome.result, "detail": outcome.detail, "proofs": list(outcome.proofs)}


def run_check(ctx: ToolContext, a: RunCheck, operation_id: str) -> dict:
    def resume(outcome: qa.CheckOutcome) -> tuple[str, str, str, str]:
        return _recorded(ctx, operation_id, "run_check", _check_result(outcome))

    outcome = qa.run(ctx.sandbox, ctx.ledger, ctx.project, ctx.ticket_id, ctx.actor, a.check, a.file, resume)
    return _check_result(outcome)


def _seen_proof(ctx: ToolContext, file: str) -> str:
    """A proof of the current version that this instance really opened."""
    digest = sha256_under(ctx.work, file)
    if f"{file}:{digest}" in viewed(ctx):  # the image itself, already opened at this version
        return file
    seen = viewed(ctx)
    for proof in ctx.ledger.renders_of(ctx.project, file, digest):
        if f"{proof}:{sha256_under(ctx.work, proof)}" in seen:  # the proof as it is now, not an older one
            return proof
    raise Refused(f"{file}: non hai guardato un render della versione attuale. render, poi view_image.")


def observe(ctx: ToolContext, a: Observe, operation_id: str) -> dict:
    if len(a.seen.strip()) < 40:
        raise Refused("descrivi cosa hai visto, con almeno una frase concreta")
    if registry.CHECKS.get(a.check, {}).get("kind") != CheckKind.OBSERVATION:
        raise Refused(f"{a.check} non è un controllo di osservazione")
    proof = _seen_proof(ctx, a.file)
    value = {"ok": True, "check": a.check, "result": a.result, "proof": proof}
    evidence.record(
        ctx.ledger,
        ctx.work,
        ctx.project,
        a.file,
        a.check,
        a.result,
        ctx.actor,
        ctx.ticket_id,
        proof,
        a.seen,
        operation=_recorded(ctx, operation_id, "observe", value),
    )
    return value


def judge(ctx: ToolContext, a: Judge, operation_id: str) -> dict:
    if registry.CHECKS.get(a.check, {}).get("kind") != CheckKind.JUDGEMENT:
        raise Refused(f"{a.check} non è un giudizio")
    if len(a.why.strip()) < 60:
        raise Refused("motiva con elementi visibili del confronto")
    missing = [path for path in a.compare if not is_file_under(ctx.work, path)]
    if missing:
        raise Refused(f"termini di confronto inesistenti: {missing}")
    if os.path.normpath(a.file) in {os.path.normpath(path) for path in a.compare}:
        raise Refused("un file non si confronta con se stesso")
    proof = _seen_proof(ctx, a.file)
    note = f"confronto con {', '.join(a.compare)}: {a.why.strip()}"
    value = {"ok": True, "check": a.check, "result": a.result}
    evidence.record(
        ctx.ledger,
        ctx.work,
        ctx.project,
        a.file,
        a.check,
        a.result,
        ctx.actor,
        ctx.ticket_id,
        proof,
        note,
        a.compare,
        operation=_recorded(ctx, operation_id, "judge", value),
    )
    return value


def record_requirement(ctx: ToolContext, a: RecordRequirement, operation_id: str) -> dict:
    kind = registry.CHECKS.get(a.check, {}).get("kind")
    if kind in (CheckKind.OBSERVATION, CheckKind.JUDGEMENT, CheckKind.MEASURE) or a.check in qa.RUNNABLE:
        raise Refused(f"{a.check} ha il suo strumento: run_check, observe o judge")
    value = {"ok": True}
    evidence.record(
        ctx.ledger,
        ctx.work,
        ctx.project,
        a.file,
        a.check,
        a.result,
        ctx.actor,
        ctx.ticket_id,
        note=a.note,
        operation=_recorded(ctx, operation_id, "record_requirement", value),
    )
    return value


TOOLS: tuple[Tool, ...] = (
    Tool("run_check", f"Esegue un controllo: {', '.join(qa.RUNNABLE)}.", RunCheck, run_check),
    Tool("observe", "Registra ciò che hai visto in un render guardato.", Observe, observe),
    Tool("judge", "Registra un giudizio con un confronto visivo.", Judge, judge),
    Tool("record_requirement", "Registra un requisito verificato.", RecordRequirement, record_requirement),
)
