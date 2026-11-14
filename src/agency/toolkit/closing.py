"""The agent tools that close a ticket: deliver it, or block it with the reason."""

from __future__ import annotations

from agency.contracts.artifact import Origin
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import (
    Action,
    Status,
    TicketType,
    Verdict,
)
from agency.qa import delivery
from agency.toolkit.base import (
    Refused,
    Strict,
    Tool,
    ToolContext,
    replayed,
)
from agency.workshop.files import (
    sha256_under,
)


class Deliver(Strict):
    note: str
    verdict: Verdict | None


class Block(Strict):
    reason: str


def deliver(ctx: ToolContext, a: Deliver, _: str) -> dict:
    if replayed(ctx, Status.DELIVERED, Action.DELIVER):
        ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.note)
        return {"ok": True, "status": "delivered"}
    spec = ctx.ledger.spec(ctx.ticket_id)
    present, problems = delivery.delivery_problems(
        ctx.ledger,
        ctx.project,
        ctx.sandbox,
        spec,
        a.verdict,
        inputs=ctx.ledger.inputs(ctx.ticket_id),
    )
    if problems:
        raise Refused("consegna rifiutata:\n" + "\n".join(problems[:20]))
    hashes = {path: sha256_under(ctx.work, path) for path in present}
    reworked = any(event.action == "rework" for event in ctx.ledger.history(ctx.ticket_id))
    if spec.type is TicketType.PRODUCTION and reworked and hashes == ctx.ledger.delivered(ctx.ticket_id):
        raise Refused("consegna rifiutata: gli output sono identici alla versione rimandata indietro")
    kept = ctx.keep(present, Origin.DELIVERY)
    ctx.ledger.apply(ctx.ticket_id, Action.DELIVER, ctx.actor, a.note, a.verdict, kept)
    ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.note)
    return {"ok": True, "status": "delivered"}


def block(ctx: ToolContext, a: Block, _: str) -> dict:
    if replayed(ctx, Status.BLOCKED, Action.BLOCK):
        ctx.finished = Outcome(state=OutcomeState.BLOCKED, note=a.reason)
        return {"ok": True, "status": "blocked"}
    ctx.ledger.apply(ctx.ticket_id, Action.BLOCK, ctx.actor, a.reason)
    ctx.finished = Outcome(state=OutcomeState.BLOCKED, note=a.reason)
    return {"ok": True, "status": "blocked"}


TOOLS: tuple[Tool, ...] = (
    Tool(
        "deliver",
        "Consegna il ticket. verdict solo per qa e revisione.",
        Deliver,
        deliver,
        strict=True,
        closes=OutcomeState.DELIVERED,
    ),
    Tool(
        "block",
        "Ferma il ticket con il motivo.",
        Block,
        block,
        strict=True,
        closes=OutcomeState.BLOCKED,
    ),
)
