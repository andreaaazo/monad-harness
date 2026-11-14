"""What the model can do: typed tools, signed by the harness, never a shell."""

from __future__ import annotations

import json

from pydantic import Field, ValidationError

from agency import registry
from agency.contracts.artifact import Origin
from agency.contracts.concept import ConceptCard, ConceptStatus
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import (
    RUNNABLE,
    Action,
    Medium,
    Status,
    TicketSpec,
    TicketType,
)
from agency.ledger import ForbiddenAction, IllegalTransition
from agency.ledger.models import ConceptRow
from agency.qa import delivery, evidence
from agency.toolkit import closing, craft, files, review
from agency.toolkit.base import (
    Refused,
    Strict,
    Tool,
    ToolContext,
    definition,
    replayed,
    result_text,
    tracer,
    viewed,
)
from agency.workshop import board, presentation
from agency.workshop.files import (
    MAX_TEXT_FILE_BYTES,
    OutsidePerimeter,
    clip,
    ensure_dir_under,
    is_file_under,
    read_under,
    replace_under,
    sha256_under,
)


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


class BoardRating(Strict):
    letter: str
    first_look: str = Field(description="Cosa si vede davvero al primo sguardo, senza spiegazioni")
    passes: bool = Field(description="Vero solo se il segno si capisce e si ricorda da solo")


class RateBoard(Strict):
    ratings: list[BoardRating] = Field(min_length=1)


class SelectConcepts(Strict):
    chosen: list[str] = Field(description="Lettere anonime delle idee da sviluppare; vuoto = nessuna regge")
    reasons: str


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


class RejectConcept(Strict):
    reason: str


def _coming(ctx: ToolContext) -> set[str]:
    """The files this work plans to produce; those asked of reviewers do not count."""
    specs = [ctx.ledger.spec(ticket) for ticket in (ctx.ticket_id, *ctx.ledger.children(ctx.ticket_id))]
    return {output for spec in specs if spec.assignee not in registry.REVIEWERS for output in spec.outputs}


def open_ticket(ctx: ToolContext, a: OpenTicket, operation_id: str) -> dict:
    if not registry.can_open(ctx.actor, a.assignee):
        raise Refused(f"{ctx.actor} non può aprire ticket verso {a.assignee}")
    if a.assignee not in registry.ROLES:
        raise Refused(f"ruolo inesistente: {a.assignee}")
    if not registry.has_prompt(a.assignee):
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
        delivery.validate(spec)
        delivery.validate_review(spec, ctx.work, _coming(ctx))
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
    problems = delivery.acceptance_problems(ctx.ledger, ctx.project, ctx.sandbox, a.ticket)
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


def plan_exploration(ctx: ToolContext, a: PlanExploration, operation_id: str) -> dict:
    assert ctx.settings is not None
    words = [word.lower() for word in a.assets]
    banned = [item for item in a.excluded if any(word in item.lower() for word in words)]
    if banned:
        raise Refused(
            f"questi esclusi vietano una risorsa del cliente: {banned}. "
            "Si esclude un cliché di esecuzione, mai il nome o il soggetto: riscrivili."
        )
    root = ctx.ledger.spec(ctx.ticket_id)
    excluded = "\n".join(f"- {item}" for item in a.excluded)
    assets = ", ".join(a.assets)
    ensure_dir_under(ctx.work, f"explorations/r{ctx.round}")
    replace_under(
        ctx.work,
        f"explorations/r{ctx.round}/applicazioni.json",
        json.dumps([item.model_dump() for item in a.applications]).encode("utf-8"),
    )
    opened = []
    for (letter, role), lever in zip(
        registry.DIRECTIONS.items(), a.levers[: ctx.settings.explorers], strict=False
    ):
        operation = f"{operation_id}:{letter}"
        stored = ctx.ledger.operation(operation)
        if stored:
            opened.append(json.loads(stored)["ticket"])
            continue
        workspace = f"explorations/r{ctx.round}/{letter}"
        ensure_dir_under(ctx.work, workspace)
        replace_under(ctx.work, f"{workspace}/brief.md", read_under(ctx.work, "brief.md"))
        spec = TicketSpec(
            title=f"Esplorazione {letter.upper()}",
            request=f"{root.request}\n\nLEVA: {lever.lever}\n\nRISORSE DEL CLIENTE: {assets}\n\n"
            f"CLICHÉ DA EVITARE\n{excluded}",
            type=TicketType.SKETCH,
            sender=ctx.actor,
            assignee=role,
            outputs=[
                "scheda.json",
                f"schizzi-{letter}.vectorcraft",
                f"foglio-{letter}.png",
                f"schizzo-{letter}.png",
            ],
            checks={"*.vectorcraft": ["master_open"], "*.png": ["visual_review"]},
            exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
            media=[Medium.VECTOR],
            parent=ctx.ticket_id,
            workspace=workspace,
            prompt="explorer",
            effort=ctx.settings.explorer_effort,
        )
        concept = ConceptRow(
            project=ctx.project, round=ctx.round, letter=letter, lever=lever.lever, idea_ticket=""
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
    present, problems = delivery.delivery_problems(ctx.ledger, ctx.project, ctx.sandbox, spec, None)
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


def _closed_by_selection(stored: str) -> Outcome:
    chosen = SelectConcepts.model_validate_json(stored).chosen
    return Outcome(state=OutcomeState.SELECTED if chosen else OutcomeState.NO_CONCEPT, note=stored)


def _closed_by_draft(stored: str) -> Outcome | None:
    """A draft with pages leaves the instance open; one without says no proposal holds up."""
    if "pagine" in json.loads(stored):
        return None
    return Outcome(state=OutcomeState.NO_CONCEPT, note=stored)


def _closed_by_presentation(stored: str) -> Outcome:
    proposals = PresentConcepts.model_validate_json(stored).proposals
    return Outcome(state=OutcomeState.PRESENTED if proposals else OutcomeState.NO_CONCEPT, note=stored)


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        *files.TOOLS,
        *craft.TOOLS,
        *review.TOOLS,
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
        *closing.TOOLS,
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
        Tool("rate_board", "Registra il primo sguardo su ogni lettera.", RateBoard, rate_board),
        Tool(
            "select_concepts",
            "Sceglie le idee da sviluppare in proposte.",
            SelectConcepts,
            select_concepts,
            on_replay=_closed_by_selection,
        ),
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
        Tool(
            "reject_concept",
            "Boccia il concetto: si torna agli schizzi.",
            RejectConcept,
            reject_concept,
            closes=OutcomeState.CONCEPT_REJECTED,
        ),
    )
}
BASE = ["read_file", "list_files", "write_file", "read_skill", "view_image", "render", "deliver", "block"]
AUTHOR = ["craft_search", "craft_describe", "craft_run", "compute", "export_master", "run_check", "observe"]
AUTHOR += ["record_requirement"]
REVIEWER = ["run_check", "observe", "judge", "record_requirement"]
DIRECTOR = ["open_ticket", "accept_ticket", "rework_ticket", "hand_off", "observe", "judge", "run_check"]
DIRECTOR += ["reject_concept"]
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
PROPOSAL = [
    "read_file",
    "read_skill",
    "craft_search",
    "craft_describe",
    "craft_run",
    "compute",
    "export_master",
]
PROPOSAL += ["render", "view_image", "run_check", "observe", "deliver", "block"]
PLAN = ["read_file", "read_skill", "plan_exploration", "block"]
SELECT = ["read_file", "list_files", "read_skill", "view_image", "select_concepts", "block"]
PRESENT = ["read_file", "list_files", "read_skill", "view_image", "draft_presentation", "present_concepts"]
PRESENT += ["block"]
BOARD = ["read_file", "view_image", "observe", "rate_board", "write_file", "deliver", "block"]


KIND_TOOLS = {
    "director": BASE + DIRECTOR,
    "router": BASE + DIRECTOR,
    "reviewer": BASE + REVIEWER,
    "author": BASE + AUTHOR,
}


def _without_craft(role: str, names: list[str]) -> list[str]:
    """A role that lists no Craft app gets no craft_* tool, whatever set it is given."""
    if registry.ROLES[role]["craft"]:
        return names
    return [name for name in names if not name.startswith("craft_")]


def role_tools(role: str) -> list[Tool]:
    names = _without_craft(role, KIND_TOOLS[registry.ROLES[role]["tools"]])
    return [TOOLS[name] for name in sorted(names)]


def tools_for(role: str, spec: TicketSpec, mode: str = "") -> list[Tool]:
    """The set depends on the phase: who looks for the idea cannot draw, and who draws cannot finish."""
    names = {"plan": PLAN, "select": SELECT, "present": PRESENT}.get(mode)
    if names is None and spec.prompt == "critic-board":
        names = BOARD
    if names is None and spec.type is TicketType.SKETCH:
        names = EXPLORE
    if names is None and spec.type is TicketType.PROPOSAL:
        names = PROPOSAL
    if not names:
        return role_tools(role)
    return [TOOLS[name] for name in sorted(_without_craft(role, names))]


class Toolbox:
    """One instance's tools. `call` runs one: an effect already recorded is replayed, not repeated, and a
    failure goes back to the model as a refused result instead of ending work already paid for."""

    def __init__(self, context: ToolContext, tools: list[Tool] | None = None) -> None:
        self.context = context
        # The set does not change during the instance: changing it would invalidate the prompt cache.
        chosen = tools if tools is not None else role_tools(context.actor)
        self.tools = {tool.name: tool for tool in chosen}
        self._definitions = [definition(tool) for tool in self.tools.values()]

    def definitions(self) -> list[dict]:
        return self._definitions

    def call(self, tool_use_id: str, name: str, raw: dict) -> dict:
        ctx = self.context
        operation_id = f"{ctx.instance}:{tool_use_id}"
        tool = self.tools.get(name)
        if tool is None:
            return self._result(tool_use_id, f"strumento non disponibile per {ctx.actor}: {name}", True)
        if tool.effect:
            stored = ctx.ledger.operation(operation_id)
            if stored is not None:  # on resume, an effect that already happened is not repeated
                self._restore(name, stored)
                return self._result(tool_use_id, stored, False)
        with tracer.start_as_current_span("tool.call") as span:
            span.set_attributes({"agency.tool": name, "agency.instance": ctx.instance})
            try:
                arguments = tool.schema.model_validate(raw)
                value = tool.handler(ctx, arguments, operation_id)
            except ValidationError as exc:
                return self._result(tool_use_id, f"input non valido: {clip(str(exc), 800)}", True)
            except (
                Refused,
                OutsidePerimeter,
                ForbiddenAction,
                IllegalTransition,
                evidence.EvidenceRefused,
                FileNotFoundError,
                ValueError,
                RuntimeError,
                KeyError,
            ) as exc:
                span.set_attribute("agency.refused", True)
                return self._result(tool_use_id, str(exc), True)
            except Exception as exc:  # a tool failure must not bring down work already paid for
                span.record_exception(exc)
                detail = clip(f"{type(exc).__name__}: {exc}", 500)
                return self._result(tool_use_id, f"{name} non è riuscito: {detail}", True)
        if isinstance(value, list):
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": value}
        text = result_text(value)
        if tool.effect and ctx.ledger.operation(operation_id) is None:  # else the handler recorded it already
            ctx.ledger.record_operation(operation_id, ctx.instance, name, text)
        return self._result(tool_use_id, text, False)

    def _restore(self, name: str, stored: str) -> None:
        """On resume, a closing tool that already ran closes again with the same outcome."""
        tool = self.tools[name]
        if tool.closes is not None:
            self.context.finished = Outcome(state=tool.closes, note="ripreso dopo un'interruzione")
        elif tool.on_replay is not None:
            outcome = tool.on_replay(stored)
            if outcome is not None:
                self.context.finished = outcome

    @staticmethod
    def _result(tool_use_id: str, text: str, is_error: bool) -> dict:
        block: dict = {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}
        if is_error:
            block["is_error"] = True
        return block
