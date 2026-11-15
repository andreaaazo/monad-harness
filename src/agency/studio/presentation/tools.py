"""The presentation's tools: the director drafts the client's pages, looks at them, then sends them."""

from __future__ import annotations

import json

from pydantic import Field

from agency.contracts.artifact import Origin
from agency.contracts.concept import ConceptStatus
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import (
    TicketType,
)
from agency.studio.presentation import document as presentation
from agency.toolkit.base import (
    Refused,
    Strict,
    Tool,
    ToolContext,
    viewed,
)
from agency.workshop.files import (
    MAX_TEXT_FILE_BYTES,
    is_file_under,
    read_under,
    replace_under,
    sha256_under,
)


class ProposalText(Strict):
    letter: str
    title: str = Field(description="Un nome breve per la proposta")
    idea: str = Field(description="L'idea detta al cliente, nelle sue parole, senza gergo")
    why: str = Field(description="Perché è giusta per questo cliente, legata a un fatto concreto")
    risk: str = Field(description="Il limite o il rischio di questa proposta, detto onestamente")


class PresentConcepts(Strict):
    proposals: list[ProposalText] = Field(description="Le proposte da mostrare; vuoto = nessuna regge")
    recommended: str | None
    reasons: str


class ConfirmPresentation(Strict):
    pass


def _delivered_proposal(ctx: ToolContext, letter: str) -> dict[str, str]:
    """What the proposal ticket delivered, by path relative to its folder; empty if it delivered nothing."""
    title = f"Proposta {letter} r{ctx.round}"
    for ticket in ctx.ledger.children(ctx.ticket_id):
        spec = ctx.ledger.spec(ticket)
        if spec.type is TicketType.PROPOSAL and spec.title == title:
            return ctx.ledger.delivered(ticket)
    return {}


def draft_presentation(ctx: ToolContext, a: PresentConcepts, _: str) -> dict:
    """Builds the real pages: the director sees what the client will see, not the texts the director wrote."""
    available = {
        row.anon
        for row in ctx.ledger.concepts(ctx.project, ctx.round)
        if row.status == ConceptStatus.PROPOSAL
    }
    letters = [item.letter for item in a.proposals]
    unknown = sorted(set(letters) - available)
    if unknown:
        raise Refused(f"proposte inesistenti: {unknown}. Disponibili: {sorted(available)}")
    if not letters:
        ctx.finished = Outcome(state=OutcomeState.NO_CONCEPT, note=a.model_dump_json())
        return a.model_dump()
    if a.recommended not in letters:
        raise Refused("lo studio raccomanda una delle proposte che presenta")
    items = [
        presentation.Proposal(
            item.letter,
            item.title,
            item.idea,
            item.why,
            item.risk,
            *presentation.proposal_files(
                ctx.work, ctx.round, item.letter, _delivered_proposal(ctx, item.letter)
            ),
        )
        for item in a.proposals
    ]
    folder = ctx.work.resolve() / presentation.folder_of(ctx.round)
    pages = presentation.build(items, str(a.recommended), a.reasons, folder)
    replace_under(ctx.work, f"{presentation.folder_of(ctx.round)}/testi.json", a.model_dump_json().encode())
    return {
        "pagine": [str(page.relative_to(ctx.work.resolve())) for page in pages],
        "poi": "Guarda ogni pagina con view_image. Se serve, rifai la bozza. Poi present_concepts.",
    }


def _drafted_pages(ctx: ToolContext) -> list[str]:
    """The pages the last draft of this instance made, as the ledger recorded them, not as the folder has."""
    drafts = [row for row in ctx.ledger.operations(ctx.instance) if row.tool == "draft_presentation"]
    if not drafts:
        return []
    latest = max(enumerate(drafts), key=lambda item: (item[1].at, item[0]))[1]
    return list(json.loads(latest.result_json).get("pagine", []))


def present_concepts(ctx: ToolContext, _a: ConfirmPresentation, __: str) -> dict:
    """Sends the client the last draft, only if it is exactly the one looked at."""
    draft = f"{presentation.folder_of(ctx.round)}/testi.json"
    pages = _drafted_pages(ctx)
    if not pages or not is_file_under(ctx.work, draft):
        raise Refused("non c'è ancora una bozza: prima draft_presentation")
    gone = [page for page in pages if not is_file_under(ctx.work, page)]
    if gone:
        raise Refused(f"mancano pagine della bozza: {gone}. Rifai la bozza con draft_presentation.")
    seen = viewed(ctx)
    missing = [page for page in pages if f"{page}:{sha256_under(ctx.work, page)}" not in seen]
    if missing:
        raise Refused(f"guarda queste pagine, così come sono ora, prima di mandarle al cliente: {missing}")
    text = read_under(ctx.work, draft, MAX_TEXT_FILE_BYTES).decode("utf-8")
    ctx.keep([presentation.pdf_of(ctx.round)], Origin.PRESENTATION)
    ctx.finished = Outcome(state=OutcomeState.PRESENTED, note=text)
    return json.loads(text)


def _closed_by_draft(stored: str) -> Outcome | None:
    """A draft with pages leaves the instance open; one without says no proposal holds up."""
    if "pagine" in json.loads(stored):
        return None
    return Outcome(state=OutcomeState.NO_CONCEPT, note=stored)


def _closed_by_presentation(stored: str) -> Outcome:
    proposals = PresentConcepts.model_validate_json(stored).proposals
    return Outcome(state=OutcomeState.PRESENTED if proposals else OutcomeState.NO_CONCEPT, note=stored)


PRESENT = ["read_file", "list_files", "read_skill", "view_image", "draft_presentation", "present_concepts"]


PRESENT += ["block"]


TOOLS: tuple[Tool, ...] = (
    Tool(
        "draft_presentation",
        "Compone le pagine per il cliente, da guardare. Vuoto = nessuna proposta regge.",
        PresentConcepts,
        draft_presentation,
        on_replay=_closed_by_draft,
    ),
    Tool(
        "present_concepts",
        "Manda al cliente l'ultima bozza, dopo averne guardato ogni pagina.",
        ConfirmPresentation,
        present_concepts,
        on_replay=_closed_by_presentation,
    ),
)
