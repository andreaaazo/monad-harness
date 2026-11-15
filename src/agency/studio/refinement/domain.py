"""The refinement's rules: pure, with no ledger, no files and no framework (ADR-0058)."""

from __future__ import annotations

from agency.contracts.registry import StudioRules
from agency.contracts.ticket import Medium, TicketSpec, TicketType

MIN_REWORK_NOTE = 10  # characters: a shorter note cannot say what to change
MIN_REJECTION_REASON = 20  # characters: a shorter reason cannot carry the evidence


def opening_refusal(rules: StudioRules, actor: str, assignee: str) -> str | None:
    """Why `actor` cannot open a ticket for `assignee`: the org chart does not allow it, the role does not
    exist, or the role has no prompt yet and cannot receive work."""
    if not rules.can_open(actor, assignee):
        return f"{actor} non può aprire ticket verso {assignee}"
    if assignee not in rules.roles:
        return f"ruolo inesistente: {assignee}"
    if assignee not in rules.active:
        return f"{assignee} non è ancora attivo nello studio: affida il lavoro a un altro ruolo"
    return None


def rework_refusal(note: str) -> str | None:
    """Why a ticket cannot be sent back with this note: it does not say what to change."""
    if len(note.strip()) < MIN_REWORK_NOTE:
        return "scrivi cosa va cambiato"
    return None


def rejection_refusal(reason: str) -> str | None:
    """Why the concept cannot be rejected with this reason: it carries no evidence that the concept, not its
    execution, fails."""
    if len(reason.strip()) < MIN_REJECTION_REASON:
        return "spiega con una prova perché il concetto, e non l'esecuzione, non regge"
    return None


def production_title(anon: str, turn: int) -> str:
    """The finisher's ticket, one per round: a rejected concept makes way for the new one."""
    return f"Rifinitura {anon} r{turn}"


def production_spec(
    *,
    root: TicketSpec,
    title: str,
    card_json: str,
    client_note: str,
    folder: str,
    letter: str,
    parent: str,
) -> TicketSpec:
    """The finisher's ticket: the client's contract, with the chosen concept and what the client said. The
    critique is the client's at the final gate, so it leaves the checks."""
    return TicketSpec(
        title=title,
        request=f"{root.request}\n\nCONCETTO SCELTO DAL CLIENTE\n{card_json}\n\n"
        f"Il cliente ha detto: {client_note}",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=root.outputs,
        checks={
            pattern: [name for name in names if name != "critique"] for pattern, names in root.checks.items()
        },
        exempt=root.exempt,
        media=[Medium.VECTOR],
        inputs=[f"{folder}/scheda.json", f"{folder}/proposta-{letter}.png"],
        parent=parent,
        prompt="finisher",
    )
