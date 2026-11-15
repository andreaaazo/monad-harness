"""The refinement's director tools: open, accept and send back tickets, hand off, reject the concept."""

from __future__ import annotations

from pydantic import Field

from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import RUNNABLE, Action, Medium, Status, TicketSpec, TicketType
from agency.qa import delivery
from agency.toolkit.base import Refused, Strict, Tool, ToolContext, replayed
from agency.workshop.files import is_file_under, sha256_under


class OpenTicket(Strict):
    title: str
    request: str
    type: TicketType
    assignee: str
    outputs: list[str]
    checks: dict[str, list[str]]
    media: list[Medium] = Field(default_factory=list)
    medium_why: str | None = None
    inputs: list[str] = Field(default_factory=list)
    exempt: dict[str, str] = Field(default_factory=dict)
    no_master: dict[str, str] = Field(default_factory=dict)


class TicketRef(Strict):
    ticket: str
    note: str = ""


class HandOff(Strict):
    note: str


class RejectConcept(Strict):
    reason: str


def _coming(ctx: ToolContext) -> set[str]:
    """The files this work plans to produce; those asked of reviewers do not count."""
    specs = [ctx.ledger.spec(ticket) for ticket in (ctx.ticket_id, *ctx.ledger.children(ctx.ticket_id))]
    return {output for spec in specs if spec.assignee not in ctx.rules.reviewers() for output in spec.outputs}


def open_ticket(ctx: ToolContext, a: OpenTicket, operation_id: str) -> dict:
    if not ctx.rules.can_open(ctx.actor, a.assignee):
        raise Refused(f"{ctx.actor} non può aprire ticket verso {a.assignee}")
    if a.assignee not in ctx.rules.roles:
        raise Refused(f"ruolo inesistente: {a.assignee}")
    if a.assignee not in ctx.rules.active:
        raise Refused(f"{a.assignee} non è ancora attivo nello studio: affida il lavoro a un altro ruolo")
    missing = [path for path in a.inputs if not is_file_under(ctx.work, path)]
    if missing:
        raise Refused(f"input inesistenti: {missing}")
    try:
        spec = TicketSpec(
            title=a.title,
            request=a.request,
            type=a.type,
            sender=ctx.actor,
            assignee=a.assignee,
            outputs=a.outputs,
            checks=a.checks,
            media=a.media,
            medium_why=a.medium_why,
            inputs=a.inputs,
            exempt=a.exempt,
            no_master=a.no_master,
            parent=ctx.ticket_id,
        )
        delivery.validate(spec, ctx.rules)
        delivery.validate_review(spec, ctx.work, _coming(ctx), ctx.rules)
    except (ValueError, delivery.ContractRefused) as exc:
        raise Refused(str(exc)) from exc
    hashes = {path: sha256_under(ctx.work, path) for path in a.inputs}
    ticket = ctx.ledger.open(spec, ctx.project, hashes, (operation_id, ctx.instance, "open_ticket"))
    return {"ok": True, "ticket": ticket}


def _own_child(ctx: ToolContext, ticket: str) -> None:
    if ctx.ledger.spec(ticket).sender != ctx.actor:
        raise Refused(f"{ticket} non è un tuo ticket")


def accept_ticket(ctx: ToolContext, a: TicketRef, _: str) -> dict:
    _own_child(ctx, a.ticket)
    if replayed(ctx, Status.ACCEPTED, Action.ACCEPT, a.ticket):
        return {"ok": True, "status": "accepted"}
    problems = delivery.acceptance_problems(ctx.ledger, ctx.project, ctx.sandbox, a.ticket, ctx.rules)
    if problems:
        raise Refused("accettazione rifiutata:\n" + "\n".join(problems[:12]))
    ctx.ledger.apply(a.ticket, Action.ACCEPT, ctx.actor, a.note)
    return {"ok": True, "status": "accepted"}


def rework_ticket(ctx: ToolContext, a: TicketRef, _: str) -> dict:
    _own_child(ctx, a.ticket)
    if replayed(ctx, Status.REWORK, Action.REWORK, a.ticket):
        return {"ok": True, "status": "rework"}
    if len(a.note.strip()) < 10:
        raise Refused("scrivi cosa va cambiato")
    ctx.ledger.apply(a.ticket, Action.REWORK, ctx.actor, a.note)
    return {"ok": True, "status": "rework"}


def hand_off(ctx: ToolContext, a: HandOff, _: str) -> dict:
    waiting = [
        ticket for ticket in ctx.ledger.children(ctx.ticket_id) if ctx.ledger.status(ticket)[0] in RUNNABLE
    ]
    if not waiting:
        raise Refused("nessun ticket figlio da eseguire: apri i ticket, oppure consegna")
    ctx.finished = Outcome(state=OutcomeState.HANDED_OFF, note=a.note)
    return {"ok": True, "waiting": waiting}


def reject_concept(ctx: ToolContext, a: RejectConcept, _: str) -> dict:
    if len(a.reason.strip()) < 20:
        raise Refused("spiega con una prova perché il concetto, e non l'esecuzione, non regge")
    for ticket in ctx.ledger.children(ctx.ticket_id):
        if ctx.ledger.status(ticket)[0] in (
            Status.OPEN,
            Status.REWORK,
            Status.DELIVERED,
            Status.BLOCKED,
        ):
            ctx.ledger.apply(ticket, Action.CANCEL, ctx.actor, "concetto bocciato")
    ctx.finished = Outcome(state=OutcomeState.CONCEPT_REJECTED, note=a.reason)
    return {"ok": True}


TOOLS: tuple[Tool, ...] = (
    Tool("open_ticket", "Apre un ticket verso un altro ruolo.", OpenTicket, open_ticket),
    Tool("accept_ticket", "Accetta un ticket consegnato che hai aperto.", TicketRef, accept_ticket),
    Tool("rework_ticket", "Rimanda un ticket con ciò che va cambiato.", TicketRef, rework_ticket),
    Tool(
        "hand_off",
        "Termina il turno in attesa dei ticket figli.",
        HandOff,
        hand_off,
        closes=OutcomeState.HANDED_OFF,
    ),
    Tool(
        "reject_concept",
        "Boccia il concetto: si torna agli schizzi.",
        RejectConcept,
        reject_concept,
        closes=OutcomeState.CONCEPT_REJECTED,
    ),
)
