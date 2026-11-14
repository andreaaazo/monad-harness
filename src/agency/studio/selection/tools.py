"""The selection's tools: the critic's first look at the anonymous board, and the director's choice of
ideas."""

from __future__ import annotations

import json

from pydantic import Field

from agency.contracts.concept import ConceptStatus
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.toolkit.base import (
    Refused,
    Strict,
    Tool,
    ToolContext,
)
from agency.workshop.files import (
    ensure_dir_under,
    replace_under,
)


class BoardRating(Strict):
    letter: str
    first_look: str = Field(description="Cosa si vede davvero al primo sguardo, senza spiegazioni")
    passes: bool = Field(description="Vero solo se il segno si capisce e si ricorda da solo")


class RateBoard(Strict):
    ratings: list[BoardRating] = Field(min_length=1)


class SelectConcepts(Strict):
    chosen: list[str] = Field(description="Lettere anonime delle idee da sviluppare; vuoto = nessuna regge")
    reasons: str


def rate_board(ctx: ToolContext, a: RateBoard, _: str) -> dict:
    """The critic's first look, without the reasoning behind the ideas: it decides who can go ahead."""
    letters = {row.anon for row in ctx.ledger.concepts(ctx.project, ctx.round) if row.anon}
    rated = {item.letter for item in a.ratings}
    if rated != letters:
        raise Refused(f"valuta tutte e sole le lettere della tavola: {sorted(letters)}")
    assert ctx.settings is not None
    data = json.dumps([item.model_dump() for item in a.ratings], ensure_ascii=False).encode("utf-8")
    # The harness copy is the one `select_concepts` trusts: the sandbox can write the one in the work folder.
    kept = ctx.settings.layout.ratings(parse_project_name(ctx.project), ctx.round)
    kept.parent.mkdir(parents=True, exist_ok=True)
    replace_under(kept.parent, kept.name, data)
    ensure_dir_under(ctx.work, "reviews")
    replace_under(ctx.work, "reviews/valutazione.json", data)
    return {"ok": True, "passano": sorted(item.letter for item in a.ratings if item.passes)}


def select_concepts(ctx: ToolContext, a: SelectConcepts, _: str) -> dict:
    available = {row.anon: row for row in ctx.ledger.concepts(ctx.project, ctx.round) if row.anon}
    unknown = sorted(set(a.chosen) - set(available))
    if unknown:
        raise Refused(f"lettere inesistenti: {unknown}. Disponibili: {sorted(available)}")
    if len(a.chosen) > 3:
        raise Refused("si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto")
    if a.chosen:
        assert ctx.settings is not None
        kept = ctx.settings.layout.ratings(parse_project_name(ctx.project), ctx.round)
        if not kept.is_file():
            raise Refused(f"la tavola del giro {ctx.round} non è stata valutata con rate_board")
        passed = {item["letter"] for item in json.loads(kept.read_text(encoding="utf-8")) if item["passes"]}
        failed = sorted(set(a.chosen) - passed)
        if failed:
            raise Refused(
                f"{failed} non hanno passato il primo sguardo: un segno che ha bisogno di spiegazioni non va "
                "avanti. Scegli tra quelli che passano, o passa chosen vuoto per esplorare di nuovo."
            )
    for anon in a.chosen:
        ctx.ledger.update_concept(available[anon].idea_ticket, status=ConceptStatus.SELECTED)
    state = OutcomeState.SELECTED if a.chosen else OutcomeState.NO_CONCEPT
    ctx.finished = Outcome(state=state, note=a.model_dump_json())
    return a.model_dump()


def _closed_by_selection(stored: str) -> Outcome:
    chosen = SelectConcepts.model_validate_json(stored).chosen
    return Outcome(state=OutcomeState.SELECTED if chosen else OutcomeState.NO_CONCEPT, note=stored)


SELECT = ["read_file", "list_files", "read_skill", "view_image", "select_concepts", "block"]


BOARD = ["read_file", "view_image", "observe", "rate_board", "write_file", "deliver", "block"]


TOOLS: tuple[Tool, ...] = (
    Tool("rate_board", "Registra il primo sguardo su ogni lettera.", RateBoard, rate_board),
    Tool(
        "select_concepts",
        "Sceglie le idee da sviluppare in proposte.",
        SelectConcepts,
        select_concepts,
        on_replay=_closed_by_selection,
    ),
)
