"""The exploration's tools: the director's plan of levers, and the explorer's concept card with its
sketches."""

from __future__ import annotations

import json

from pydantic import Field

from agency.contracts.artifact import Origin
from agency.contracts.concept import ConceptCard, ConceptStatus
from agency.contracts.ledger import ConceptEntry
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import Action, Status
from agency.qa import delivery
from agency.studio.exploration.domain import banned_exclusions, exploration_spec, explorer_assignments
from agency.toolkit.base import Refused, Strict, Tool, ToolContext, replayed
from agency.workshop import board
from agency.workshop.files import ensure_dir_under, read_under, replace_under, sha256_under


class Lever(Strict):
    lever: str = Field(description="Da dove parte l'esploratore: un ingresso al significato, non uno stile")


class Application(Strict):
    name: str = Field(description="Un uso reale del cliente, per esempio l'insegna")
    size: str = Field(description="Dimensione d'uso reale, per esempio 16 mm di larghezza")


class PlanExploration(Strict):
    levers: list[Lever] = Field(min_length=2, max_length=5)
    assets: list[str] = Field(
        min_length=1,
        description="Parole chiave delle risorse forti del cliente: nome, soggetto, figura. Mai vietate",
    )
    excluded: list[str] = Field(min_length=3, description="Cliché di esecuzione da evitare, mai una risorsa")
    applications: list[Application] = Field(
        min_length=2, max_length=4, description="Dove il cliente vedrà ogni proposta: dal suo mondo reale"
    )


def plan_exploration(ctx: ToolContext, a: PlanExploration, operation_id: str) -> dict:
    assert ctx.settings is not None
    banned = banned_exclusions(a.assets, a.excluded)
    if banned:
        raise Refused(
            f"questi esclusi vietano una risorsa del cliente: {banned}. "
            "Si esclude un cliché di esecuzione, mai il nome o il soggetto: riscrivili."
        )
    root = ctx.ledger.spec(ctx.ticket_id)
    ensure_dir_under(ctx.work, f"explorations/r{ctx.round}")
    replace_under(
        ctx.work,
        f"explorations/r{ctx.round}/applicazioni.json",
        json.dumps([item.model_dump() for item in a.applications]).encode("utf-8"),
    )
    opened = []
    levers = [item.lever for item in a.levers]
    for letter, role, lever in explorer_assignments(ctx.rules.directions(), levers, ctx.settings.explorers):
        operation = f"{operation_id}:{letter}"
        stored = ctx.ledger.operation(operation)
        if stored:
            opened.append(json.loads(stored)["ticket"])
            continue
        workspace = f"explorations/r{ctx.round}/{letter}"
        ensure_dir_under(ctx.work, workspace)
        replace_under(ctx.work, f"{workspace}/brief.md", read_under(ctx.work, "brief.md"))
        spec = exploration_spec(
            root_request=root.request,
            letter=letter,
            role=role,
            lever=lever,
            assets=a.assets,
            excluded=a.excluded,
            sender=ctx.actor,
            parent=ctx.ticket_id,
            workspace=workspace,
            effort=ctx.settings.explorer_effort,
        )
        concept = ConceptEntry(
            project=ctx.project, round=ctx.round, letter=letter, lever=lever, idea_ticket=""
        )
        ticket = ctx.ledger.open(
            spec, ctx.project, operation=(operation, ctx.instance, "plan_exploration"), concept=concept
        )
        opened.append(ticket)
    ctx.finished = Outcome(state=OutcomeState.HANDED_OFF, note=f"esplorazione con {len(opened)} leve")
    return {"ok": True, "tickets": opened}


def submit_concept(ctx: ToolContext, a: ConceptCard, _: str) -> dict:
    """Closes the exploration: the card counts only together with the sketches looked at."""
    if replayed(ctx, Status.DELIVERED, Action.DELIVER):
        ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.concept)
        return {"ok": True}
    replace_under(ctx.work, "scheda.json", a.model_dump_json(indent=2).encode("utf-8"))
    spec = ctx.ledger.spec(ctx.ticket_id)
    present, problems = delivery.delivery_problems(
        ctx.ledger, ctx.project, ctx.sandbox, spec, None, rules=ctx.rules
    )
    if problems:
        raise Refused("consegna rifiutata:\n" + "\n".join(problems[:20]))
    sketch = next(path for path in spec.outputs if path.startswith("schizzo-"))
    digest = sha256_under(ctx.work, sketch)
    warning = board.mark_problem(ctx.work.resolve() / sketch)
    if warning and ctx.warned_sketch != digest:
        ctx.warned_sketch = digest
        raise Refused(warning)
    kept = ctx.keep(present, Origin.DELIVERY)
    ctx.ledger.update_concept(ctx.ticket_id, card_json=a.model_dump_json(), status=ConceptStatus.SKETCH)
    ctx.ledger.apply(ctx.ticket_id, Action.DELIVER, ctx.actor, a.concept, delivered=kept)
    ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.concept)
    return {"ok": True}


EXPLORE = ["read_file", "list_files", "read_skill", "craft_search", "craft_describe", "craft_run"]
EXPLORE += [
    "compute",
    "export_master",
    "render",
    "view_image",
    "run_check",
    "observe",
    "submit_concept",
    "block",
]
PLAN = ["read_file", "read_skill", "plan_exploration", "block"]


TOOLS: tuple[Tool, ...] = (
    Tool(
        "plan_exploration",
        "Avvia gli esploratori con leve diverse.",
        PlanExploration,
        plan_exploration,
        closes=OutcomeState.HANDED_OFF,
    ),
    Tool(
        "submit_concept",
        "Consegna scheda e schizzi: chiude l'esplorazione.",
        ConceptCard,
        submit_concept,
        closes=OutcomeState.DELIVERED,
    ),
)
