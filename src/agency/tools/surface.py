"""Ciò che il modello può fare: strumenti tipizzati, firmati dall'harness, mai una shell."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Any

from opentelemetry import trace
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agency.agents import prompts
from agency.artifacts import keeping
from agency.config import Settings
from agency.contracts.artifact import ArtifactStore, Origin
from agency.contracts.concept import ConceptCard
from agency.contracts.media import media_type, open_image
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.ticket import REVIEWERS, Action, Medium, Status, TicketSpec, TicketType, Verdict
from agency.ledger import ForbiddenAction, IllegalTransition, Ledger
from agency.ledger.models import ConceptRow
from agency.qa import checks as qa
from agency.qa import delivery, evidence
from agency.tools import board, craft, master, presentation, render
from agency.tools.files import (
    OutsidePerimeter,
    clip,
    ensure_dir_under,
    inside,
    open_under,
    read_under,
    replace_under,
    sha256,
    sha256_under,
)
from agency.tools.sandbox import OPS, Sandbox

tracer = trace.get_tracer("agency.tools")
TEXT_FILES = (".md", ".txt", ".json")
EXPORT_OPTIONS = {"--artboard", "--range", "--scale", "--outline-text", "--decimals"}
IMAGE_SIDE = 1600
IMAGE_BYTES = 3_500_000
MAX_IMAGE_FILE_BYTES = 64 * 2**20
IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
# The harness's folders in /job, which list_files does not show. `.ops` held its files before ADR-0044 and can
# still be in an older work folder.
HIDDEN = frozenset({".ops", craft.PARTIAL})
NO_OPS = "{tool} non è disponibile in questa sandbox: manca la cartella /ops"


class Refused(Exception):
    """Azione rifiutata: il motivo torna al modello, che può correggersi."""


@dataclass
class ToolContext:
    actor: str
    project: str
    ticket_id: str
    instance: str
    ledger: Ledger
    sandbox: Sandbox
    index: craft.CommandIndex
    artifacts: ArtifactStore
    finished: Outcome | None = None
    warned_sketch: str = ""  # sha256 dello schizzo già avvisato: l'avviso vale una volta per versione
    mode: str = ""
    round: int = 1
    settings: Settings | None = None
    run: int | None = None  # l'esecuzione in corso: None fuori da una sessione

    @property
    def work(self) -> Path:
        return self.sandbox.work

    @cached_property
    def finisher_outputs(self) -> tuple[str, ...]:
        """I master di un rifinitore: il concetto è scelto, e lavora solo su quelli. Vuoto per gli altri."""
        try:
            spec = self.ledger.spec(self.ticket_id)
        except KeyError:
            return ()
        return tuple(spec.outputs) if spec.prompt == "finisher" else ()

    def keep(self, paths: list[str], origin: Origin) -> dict[str, str]:
        """Conserva la versione attuale dei file prima dell'evento che la usa. Restituisce gli hash."""
        return keeping.keep(
            self.artifacts,
            self.ledger,
            self.work,
            {path: path for path in paths},
            project=self.project,
            origin=origin,
            ticket_id=self.ticket_id,
            run=self.run,
        )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadFile(Strict):
    path: str
    offset: int = 0
    limit: int = Field(default=400, le=2000)


class ListFiles(Strict):
    pattern: str = "**/*"


class WriteFile(Strict):
    path: str = Field(description="Solo .md, .txt, .json: i master si cambiano con craft_run")
    content: str


class ReadSkill(Strict):
    name: str
    file: str = Field(default="SKILL.md", description="Per name='org': craft.md, anti-patterns.md, ...")


class ViewImage(Strict):
    path: str


class Render(Strict):
    path: str
    zooms: list[list[float]] = Field(default_factory=list, description="[[x,y,w,h]] in frazioni 0-1")


class CraftSearch(Strict):
    query: str


class CraftDescribe(Strict):
    command: str


class CraftRun(Strict):
    document: str = Field(description="Master .vectorcraft nel progetto, creato se non esiste")
    steps: list[dict] = Field(description='[{"command": "path.create", "params": {...}}]')


class Compute(Strict):
    code: str = Field(description="Python senza rete. Scrive solo nella cartella del progetto.")


class ExportMaster(Strict):
    master: str
    output: str
    options: list[str] = Field(default_factory=list)


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


class Deliver(Strict):
    note: str
    verdict: Verdict | None


class Block(Strict):
    reason: str


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


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: type[BaseModel]
    handler: Callable[[ToolContext, Any, str], Any]
    effect: bool = True
    strict: bool = False


def _text_only(path: str) -> None:
    if not path.lower().endswith(TEXT_FILES):
        raise Refused(f"{path}: con write_file solo note di testo. I vettori stanno nel master.")


def read_file(ctx: ToolContext, a: ReadFile, _: str) -> dict:
    target = inside(ctx.work, a.path)
    if not target.is_file():
        raise Refused(f"{a.path}: non esiste")
    lines = read_under(ctx.work, a.path).decode("utf-8", errors="replace").splitlines()
    return {"lines": len(lines), "text": clip("\n".join(lines[a.offset : a.offset + a.limit]), 12000)}


def list_files(ctx: ToolContext, a: ListFiles, _: str) -> dict:
    if ".." in Path(a.pattern).parts:
        raise Refused("il perimetro è la cartella del lavoro: niente percorsi con ..")
    root = ctx.work.resolve()
    found = sorted(
        str(p.relative_to(ctx.work))
        for p in ctx.work.glob(a.pattern)
        if p.is_file() and HIDDEN.isdisjoint(p.parts) and p.resolve().is_relative_to(root)
    )
    return {"files": found[:200], "total": len(found)}


def write_file(ctx: ToolContext, a: WriteFile, _: str) -> dict:
    _text_only(a.path)
    if ctx.actor in REVIEWERS and not a.path.startswith("reviews/"):
        raise Refused("un revisore scrive solo in reviews/: non modifica il lavoro che giudica")
    folder = PurePosixPath(a.path).parent
    if folder.parts:
        ensure_dir_under(ctx.work, str(folder))
    replace_under(ctx.work, a.path, a.content.encode("utf-8"))
    return {"ok": True, "path": a.path}


def read_skill(_: ToolContext, a: ReadSkill, __: str) -> dict:
    if a.name != "org" and a.name not in prompts.skill_names():
        raise Refused(f"skill sconosciuta: {a.name}. Disponibili: {prompts.skills_index()}")
    root = prompts.PROMPTS / ("org" if a.name == "org" else f"skills/{a.name}")
    target = inside(root, a.file)
    if not target.is_file():
        raise Refused(f"{a.file}: non esiste in {a.name}")
    return {"text": target.read_text(encoding="utf-8")}


def _viewed(ctx: ToolContext) -> dict[str, int]:
    """Immagini davvero guardate da questa istanza, per versione: lo sa il sistema, non l'agente."""
    seen: dict[str, int] = {}
    for row in ctx.ledger.operations(ctx.instance):
        if row.tool == "view_image":
            key = json.loads(row.result_json)["key"]
            seen[key] = seen.get(key, 0) + 1
    return seen


def view_image(ctx: ToolContext, a: ViewImage, operation_id: str) -> list[dict]:
    target = inside(ctx.work, a.path)
    if target.suffix.lower() not in IMAGE_MEDIA or not target.is_file():
        raise Refused(f"{a.path}: non è un'immagine leggibile. Usa render.")
    # One read: the hash below is of the bytes that are shown. It stops one byte past the limit.
    with os.fdopen(open_under(ctx.work, a.path, os.O_RDONLY), "rb") as handle:
        raw = handle.read(MAX_IMAGE_FILE_BYTES + 1)
    if len(raw) > MAX_IMAGE_FILE_BYTES:
        raise Refused(f"{a.path}: supera il limite di {MAX_IMAGE_FILE_BYTES // 2**20} MiB per un'immagine.")
    key = f"{a.path}:{hashlib.sha256(raw).hexdigest()}"
    seen = _viewed(ctx)
    try:
        image = open_image(raw)
    except UnidentifiedImageError as exc:
        raise Refused(f"{a.path}: non è un'immagine leggibile. Usa render.") from exc
    ctx.ledger.record_operation(operation_id, ctx.instance, "view_image", json.dumps({"key": key}))
    with image:
        media = media_type(image)
        size = image.size
        reduce = max(size) > IMAGE_SIDE or len(raw) > IMAGE_BYTES
        if reduce:  # le immagini grandi si riducono da sole: non si rifiutano
            small = image.convert("RGB")
            small.thumbnail((IMAGE_SIDE, IMAGE_SIDE), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            small.save(buffer, format="PNG")
            raw = buffer.getvalue()
    data = base64.standard_b64encode(raw).decode()
    note = f"{a.path} {size[0]}×{size[1]}" + (f", mostrata ridotta a {IMAGE_SIDE} px" if reduce else "")
    if seen.get(key):
        note += ". L'avevi già guardata e non è cambiata."
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png" if reduce else media, "data": data},
        },
        {"type": "text", "text": note},
    ]


def render_tool(ctx: ToolContext, a: Render, _: str) -> dict:
    zooms = [(z[0], z[1], z[2], z[3]) for z in a.zooms]
    return {"proofs": render.render_one(ctx.sandbox, ctx.ledger, ctx.project, a.path, zooms)}


def craft_search(ctx: ToolContext, a: CraftSearch, _: str) -> dict:
    return {"commands": [{"id": c.id, "label": c.label} for c in ctx.index.search(a.query)]}


def craft_describe(ctx: ToolContext, a: CraftDescribe, _: str) -> dict:
    command = ctx.index.commands.get(a.command)
    if command is None:
        raise Refused(f"comando inesistente: {a.command}. Usa craft_search.")
    return {"id": command.id, "label": command.label, "params": command.params}


def craft_run(ctx: ToolContext, a: CraftRun, operation_id: str) -> dict:
    if not a.document.endswith(".vectorcraft"):
        raise Refused("in questa fase craft_run lavora su documenti .vectorcraft")
    outputs = ctx.finisher_outputs
    if outputs and a.document not in outputs:
        raise Refused("il concetto è scelto: lavori solo sui master in OUTPUT, niente file di esplorazione")
    safe = "".join(c if c.isalnum() else "_" for c in operation_id)
    if ctx.sandbox.ops is None or ctx.settings is None:
        raise Refused(NO_OPS.format(tool="craft_run"))
    records = ctx.settings.layout.ops_records(ctx.project, ctx.instance)
    result = craft.run_steps(ctx.sandbox, ctx.index, a.document, a.steps, safe, records)
    if not result.get("ok"):
        raise Refused(result.get("error", "esecuzione fallita"))
    return result


def compute(ctx: ToolContext, a: Compute, operation_id: str) -> dict:
    if ctx.sandbox.ops is None:
        raise Refused(NO_OPS.format(tool="compute"))
    name = "compute_" + "".join(c if c.isalnum() else "_" for c in operation_id) + ".py"
    replace_under(ctx.sandbox.ops, name, a.code.encode("utf-8"))
    done = ctx.sandbox.run([ctx.sandbox.python(), "-I", f"{OPS}/{name}"], timeout=60)
    return {"exit": done.code, "output": clip(done.output, 3000)}


def export_master(ctx: ToolContext, a: ExportMaster, _: str) -> dict:
    flags = {option for option in a.options if option.startswith("--")}
    if flags - EXPORT_OPTIONS:
        raise Refused(f"opzioni non ammesse: {sorted(flags - EXPORT_OPTIONS)}")
    error = master.export(ctx.sandbox, ctx.ledger, ctx.project, a.master, a.output, a.options)
    if error:
        raise Refused(error)
    return {"ok": True, "output": a.output}


def run_check(ctx: ToolContext, a: RunCheck, _: str) -> dict:
    outcome = qa.run(ctx.sandbox, ctx.ledger, ctx.project, ctx.ticket_id, ctx.actor, a.check, a.file)
    return {"result": outcome.result, "detail": outcome.detail, "proofs": list(outcome.proofs)}


def _seen_proof(ctx: ToolContext, file: str) -> str:
    """Una prova della versione attuale che questa istanza ha davvero aperto."""
    digest = sha256(inside(ctx.work, file))
    if f"{file}:{digest}" in _viewed(ctx):  # l'immagine stessa, già aperta in questa versione
        return file
    viewed = _viewed(ctx)
    for proof in ctx.ledger.renders_of(ctx.project, file, digest):
        if f"{proof}:{sha256_under(ctx.work, proof)}" in viewed:  # the proof as it is now, not an older one
            return proof
    raise Refused(f"{file}: non hai guardato un render della versione attuale. render, poi view_image.")


def observe(ctx: ToolContext, a: Observe, _: str) -> dict:
    if len(a.seen.strip()) < 40:
        raise Refused("descrivi cosa hai visto, con almeno una frase concreta")
    if evidence.CHECKS.get(a.check, {}).get("kind") != "observation":
        raise Refused(f"{a.check} non è un controllo di osservazione")
    proof = _seen_proof(ctx, a.file)
    evidence.record(
        ctx.ledger, ctx.work, ctx.project, a.file, a.check, a.result, ctx.actor, ctx.ticket_id, proof, a.seen
    )
    return {"ok": True, "check": a.check, "result": a.result, "proof": proof}


def judge(ctx: ToolContext, a: Judge, _: str) -> dict:
    if evidence.CHECKS.get(a.check, {}).get("kind") != "judgement":
        raise Refused(f"{a.check} non è un giudizio")
    if len(a.why.strip()) < 60:
        raise Refused("motiva con elementi visibili del confronto")
    missing = [path for path in a.compare if not inside(ctx.work, path).exists()]
    if missing:
        raise Refused(f"termini di confronto inesistenti: {missing}")
    if inside(ctx.work, a.file).resolve() in {inside(ctx.work, path).resolve() for path in a.compare}:
        raise Refused("un file non si confronta con se stesso")
    proof = _seen_proof(ctx, a.file)
    note = f"confronto con {', '.join(a.compare)}: {a.why.strip()}"
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
    )
    return {"ok": True, "check": a.check, "result": a.result}


def record_requirement(ctx: ToolContext, a: RecordRequirement, _: str) -> dict:
    kind = evidence.CHECKS.get(a.check, {}).get("kind")
    if kind in ("observation", "judgement", "measure") or a.check in qa.RUNNABLE:
        raise Refused(f"{a.check} ha il suo strumento: run_check, observe o judge")
    evidence.record(
        ctx.ledger, ctx.work, ctx.project, a.file, a.check, a.result, ctx.actor, ctx.ticket_id, note=a.note
    )
    return {"ok": True}


def _coming(ctx: ToolContext) -> set[str]:
    """I file che questo lavoro prevede di produrre: non contano quelli chiesti ai revisori."""
    specs = [ctx.ledger.spec(ticket) for ticket in (ctx.ticket_id, *ctx.ledger.children(ctx.ticket_id))]
    return {output for spec in specs if spec.assignee not in REVIEWERS for output in spec.outputs}


def open_ticket(ctx: ToolContext, a: OpenTicket, operation_id: str) -> dict:
    if not prompts.can_open(ctx.actor, a.assignee):
        raise Refused(f"{ctx.actor} non può aprire ticket verso {a.assignee}")
    if a.assignee not in prompts.ROLES:
        raise Refused(f"ruolo inesistente: {a.assignee}")
    if not prompts.has_prompt(a.assignee):
        raise Refused(f"{a.assignee} non è ancora attivo nello studio: affida il lavoro a un altro ruolo")
    missing = [path for path in a.inputs if not inside(ctx.work, path).exists()]
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
    hashes = {path: sha256(inside(ctx.work, path)) for path in a.inputs}
    ticket = ctx.ledger.open(spec, ctx.project, hashes, (operation_id, ctx.instance, "open_ticket"))
    return {"ok": True, "ticket": ticket}


def _own_child(ctx: ToolContext, ticket: str) -> None:
    if ctx.ledger.spec(ticket).sender != ctx.actor:
        raise Refused(f"{ticket} non è un tuo ticket")


def accept_ticket(ctx: ToolContext, a: TicketRef, _: str) -> dict:
    _own_child(ctx, a.ticket)
    problems = delivery.acceptance_problems(ctx.ledger, ctx.project, ctx.sandbox, a.ticket)
    if problems:
        raise Refused("accettazione rifiutata:\n" + "\n".join(problems[:12]))
    ctx.ledger.apply(a.ticket, Action.ACCEPT, ctx.actor, a.note)
    return {"ok": True, "status": "accepted"}


def rework_ticket(ctx: ToolContext, a: TicketRef, _: str) -> dict:
    _own_child(ctx, a.ticket)
    if len(a.note.strip()) < 10:
        raise Refused("scrivi cosa va cambiato")
    ctx.ledger.apply(a.ticket, Action.REWORK, ctx.actor, a.note)
    return {"ok": True, "status": "rework"}


def hand_off(ctx: ToolContext, a: HandOff, _: str) -> dict:
    waiting = [
        ticket
        for ticket in ctx.ledger.children(ctx.ticket_id)
        if ctx.ledger.status(ticket)[0] in (Status.OPEN, Status.REWORK)
    ]
    if not waiting:
        raise Refused("nessun ticket figlio da eseguire: apri i ticket, oppure consegna")
    ctx.finished = Outcome(state=OutcomeState.HANDED_OFF, note=a.note)
    return {"ok": True, "waiting": waiting}


def deliver(ctx: ToolContext, a: Deliver, _: str) -> dict:
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
    hashes = {path: sha256(inside(ctx.work, path)) for path in present}
    reworked = any(event.action == "rework" for event in ctx.ledger.history(ctx.ticket_id))
    if spec.type is TicketType.PRODUCTION and reworked and hashes == ctx.ledger.delivered(ctx.ticket_id):
        raise Refused("consegna rifiutata: gli output sono identici alla versione rimandata indietro")
    kept = ctx.keep(present, Origin.DELIVERY)
    ctx.ledger.apply(ctx.ticket_id, Action.DELIVER, ctx.actor, a.note, a.verdict, kept)
    ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.note)
    return {"ok": True, "status": "delivered"}


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
    plan_file = inside(ctx.work, f"explorations/r{ctx.round}/applicazioni.json")
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps([item.model_dump() for item in a.applications]), encoding="utf-8")
    opened = []
    for letter, lever in zip("abcde", a.levers[: ctx.settings.explorers], strict=False):
        operation = f"{operation_id}:{letter}"
        stored = ctx.ledger.operation(operation)
        if stored:
            opened.append(json.loads(stored)["ticket"])
            continue
        workspace = f"explorations/r{ctx.round}/{letter}"
        folder = inside(ctx.work, workspace)
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inside(ctx.work, "brief.md"), folder / "brief.md")
        spec = TicketSpec(
            title=f"Esplorazione {letter.upper()}",
            request=f"{root.request}\n\nLEVA: {lever.lever}\n\nRISORSE DEL CLIENTE: {assets}\n\n"
            f"CLICHÉ DA EVITARE\n{excluded}",
            type=TicketType.SKETCH,
            sender=ctx.actor,
            assignee=f"direction-{letter}",
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
        ticket = ctx.ledger.open(spec, ctx.project, operation=(operation, ctx.instance, "plan_exploration"))
        ctx.ledger.add_concept(
            ConceptRow(
                project=ctx.project, round=ctx.round, letter=letter, lever=lever.lever, idea_ticket=ticket
            )
        )
        opened.append(ticket)
    ctx.finished = Outcome(state=OutcomeState.HANDED_OFF, note=f"esplorazione con {len(opened)} leve")
    return {"ok": True, "tickets": opened}


def submit_concept(ctx: ToolContext, a: ConceptCard, _: str) -> dict:
    """Chiude l'esplorazione: la scheda vale solo insieme agli schizzi guardati."""
    target = inside(ctx.work, "scheda.json")
    target.write_text(a.model_dump_json(indent=2), encoding="utf-8")
    spec = ctx.ledger.spec(ctx.ticket_id)
    present, problems = delivery.delivery_problems(ctx.ledger, ctx.project, ctx.sandbox, spec, None)
    if problems:
        raise Refused("consegna rifiutata:\n" + "\n".join(problems[:20]))
    sketch = inside(ctx.work, next(path for path in spec.outputs if path.startswith("schizzo-")))
    digest = sha256(sketch)
    warning = board.mark_problem(sketch)
    if warning and ctx.warned_sketch != digest:
        ctx.warned_sketch = digest
        raise Refused(warning)
    kept = ctx.keep(present, Origin.DELIVERY)
    ctx.ledger.update_concept(ctx.ticket_id, card_json=a.model_dump_json(), status="schizzo")
    ctx.ledger.apply(ctx.ticket_id, Action.DELIVER, ctx.actor, a.concept, delivered=kept)
    ctx.finished = Outcome(state=OutcomeState.DELIVERED, note=a.concept)
    return {"ok": True}


def rate_board(ctx: ToolContext, a: RateBoard, _: str) -> dict:
    """Il primo sguardo del critico, che non conosce le motivazioni: decide chi può andare avanti."""
    letters = {row.anon for row in ctx.ledger.concepts(ctx.project, ctx.round) if row.anon}
    rated = {item.letter for item in a.ratings}
    if rated != letters:
        raise Refused(f"valuta tutte e sole le lettere della tavola: {sorted(letters)}")
    target = inside(ctx.work, "reviews/valutazione.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([item.model_dump() for item in a.ratings], ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True, "passano": sorted(item.letter for item in a.ratings if item.passes)}


def select_concepts(ctx: ToolContext, a: SelectConcepts, _: str) -> dict:
    available = {row.anon: row for row in ctx.ledger.concepts(ctx.project, ctx.round) if row.anon}
    unknown = sorted(set(a.chosen) - set(available))
    if unknown:
        raise Refused(f"lettere inesistenti: {unknown}. Disponibili: {sorted(available)}")
    if len(a.chosen) > 3:
        raise Refused("si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto")
    verdicts = inside(ctx.work, f"board/r{ctx.round}/reviews/valutazione.json")
    if a.chosen:
        if not verdicts.exists():
            raise Refused("manca il primo sguardo del critico: non si sceglie senza")
        passed = {
            item["letter"] for item in json.loads(verdicts.read_text(encoding="utf-8")) if item["passes"]
        }
        failed = sorted(set(a.chosen) - passed)
        if failed:
            raise Refused(
                f"{failed} non hanno passato il primo sguardo: un segno che ha bisogno di spiegazioni non va "
                "avanti. Scegli tra quelli che passano, o passa chosen vuoto per esplorare di nuovo."
            )
    for anon in a.chosen:
        ctx.ledger.update_concept(available[anon].idea_ticket, status="selezionata")
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
    """Compone le pagine vere: il direttore vede ciò che vedrà il cliente, non i testi che ha scritto."""
    available = {row.anon for row in ctx.ledger.concepts(ctx.project, ctx.round) if row.status == "proposta"}
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
    folder = inside(ctx.work, presentation.folder_of(ctx.round))
    pages = presentation.build(items, str(a.recommended), a.reasons, folder)
    (folder / "testi.json").write_text(a.model_dump_json(), encoding="utf-8")
    return {
        "pagine": [str(page.relative_to(ctx.work.resolve())) for page in pages],
        "poi": "Guarda ogni pagina con view_image. Se serve, rifai la bozza. Poi present_concepts.",
    }


def present_concepts(ctx: ToolContext, _a: ConfirmPresentation, __: str) -> dict:
    """Manda al cliente l'ultima bozza, solo se è esattamente quella guardata."""
    folder = inside(ctx.work, presentation.folder_of(ctx.round))
    draft = folder / "testi.json"
    if not draft.is_file():
        raise Refused("non c'è ancora una bozza: prima draft_presentation")
    seen = _viewed(ctx)
    pages = [str(path.relative_to(ctx.work.resolve())) for path in sorted(folder.glob("pagina-*.png"))]
    missing = [page for page in pages if f"{page}:{sha256(inside(ctx.work, page))}" not in seen]
    if missing:
        raise Refused(f"guarda queste pagine, così come sono ora, prima di mandarle al cliente: {missing}")
    text = draft.read_text(encoding="utf-8")
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


def block(ctx: ToolContext, a: Block, _: str) -> dict:
    ctx.ledger.apply(ctx.ticket_id, Action.BLOCK, ctx.actor, a.reason)
    ctx.finished = Outcome(state=OutcomeState.BLOCKED, note=a.reason)
    return {"ok": True, "status": "blocked"}


# Gli strumenti che chiudono sempre, e sempre con lo stesso esito.
CLOSE_ALWAYS: dict[str, OutcomeState] = {
    "deliver": OutcomeState.DELIVERED,
    "block": OutcomeState.BLOCKED,
    "hand_off": OutcomeState.HANDED_OFF,
    "plan_exploration": OutcomeState.HANDED_OFF,
    "submit_concept": OutcomeState.DELIVERED,
    "reject_concept": OutcomeState.CONCEPT_REJECTED,
}

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("read_file", "Legge un file di testo del progetto.", ReadFile, read_file, effect=False),
        Tool("list_files", "Elenca i file del progetto.", ListFiles, list_files, effect=False),
        Tool("write_file", "Scrive una nota di testo.", WriteFile, write_file),
        Tool(
            "read_skill", "Carica una skill o un documento dello studio.", ReadSkill, read_skill, effect=False
        ),
        Tool("view_image", "Mostra un'immagine. Costa contesto.", ViewImage, view_image, effect=False),
        Tool("render", "Rende un SVG, un master o un'immagine in PNG da guardare.", Render, render_tool),
        Tool("craft_search", "Cerca nei comandi di VectorCraft.", CraftSearch, craft_search, effect=False),
        Tool(
            "craft_describe", "Mostra i parametri di un comando.", CraftDescribe, craft_describe, effect=False
        ),
        Tool("craft_run", "Esegue passi su un master VectorCraft.", CraftRun, craft_run),
        Tool("compute", "Esegue Python isolato per calcolare geometria e misure.", Compute, compute),
        Tool("export_master", "Esporta dal master e registra il legame.", ExportMaster, export_master),
        Tool("run_check", f"Esegue un controllo: {', '.join(qa.RUNNABLE)}.", RunCheck, run_check),
        Tool("observe", "Registra ciò che hai visto in un render guardato.", Observe, observe),
        Tool("judge", "Registra un giudizio con un confronto visivo.", Judge, judge),
        Tool(
            "record_requirement", "Registra un requisito verificato.", RecordRequirement, record_requirement
        ),
        Tool("open_ticket", "Apre un ticket verso un altro ruolo.", OpenTicket, open_ticket),
        Tool("accept_ticket", "Accetta un ticket consegnato che hai aperto.", TicketRef, accept_ticket),
        Tool("rework_ticket", "Rimanda un ticket con ciò che va cambiato.", TicketRef, rework_ticket),
        Tool("hand_off", "Termina il turno in attesa dei ticket figli.", HandOff, hand_off),
        Tool(
            "deliver", "Consegna il ticket. verdict solo per qa e revisione.", Deliver, deliver, strict=True
        ),
        Tool("block", "Ferma il ticket con il motivo.", Block, block, strict=True),
        Tool(
            "plan_exploration", "Avvia gli esploratori con leve diverse.", PlanExploration, plan_exploration
        ),
        Tool(
            "submit_concept", "Consegna scheda e schizzi: chiude l'esplorazione.", ConceptCard, submit_concept
        ),
        Tool("rate_board", "Registra il primo sguardo su ogni lettera.", RateBoard, rate_board),
        Tool(
            "select_concepts", "Sceglie le idee da sviluppare in proposte.", SelectConcepts, select_concepts
        ),
        Tool(
            "draft_presentation",
            "Compone le pagine per il cliente, da guardare. Vuoto = nessuna proposta regge.",
            PresentConcepts,
            draft_presentation,
        ),
        Tool(
            "present_concepts",
            "Manda al cliente l'ultima bozza, dopo averne guardato ogni pagina.",
            ConfirmPresentation,
            present_concepts,
        ),
        Tool("reject_concept", "Boccia il concetto: si torna agli schizzi.", RejectConcept, reject_concept),
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


def role_tools(role: str) -> list[Tool]:
    if role.endswith("-director") or role == "router":
        names = BASE + DIRECTOR
    elif role in REVIEWERS:
        names = BASE + REVIEWER
    else:
        names = BASE + AUTHOR
    return [TOOLS[name] for name in sorted(names)]


def tools_for(role: str, spec: TicketSpec, mode: str = "") -> list[Tool]:
    """Il set dipende dalla fase: chi cerca l'idea non può disegnare, chi disegna non può rifinire."""
    names = {"plan": PLAN, "select": SELECT, "present": PRESENT}.get(mode)
    if names is None and spec.prompt == "critic-board":
        names = BOARD
    if names is None and spec.type is TicketType.SKETCH:
        names = EXPLORE
    if names is None and spec.type is TicketType.PROPOSAL:
        names = PROPOSAL
    return [TOOLS[name] for name in sorted(names)] if names else role_tools(role)


def definition(tool: Tool) -> dict:
    schema = tool.schema.model_json_schema()
    schema.pop("title", None)
    item = {"name": tool.name, "description": tool.description, "input_schema": schema}
    if tool.strict:
        item["strict"] = True
    else:
        item["eager_input_streaming"] = True
    return item


class Toolbox:
    def __init__(self, context: ToolContext, tools: list[Tool] | None = None) -> None:
        self.context = context
        # Il set non cambia durante l'istanza: cambiarlo invaliderebbe la cache.
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
            if stored is not None:  # alla ripresa un effetto già avvenuto non si ripete
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
            except Exception as exc:  # un guasto di uno strumento non deve far cadere un lavoro già pagato
                span.record_exception(exc)
                detail = clip(f"{type(exc).__name__}: {exc}", 500)
                return self._result(tool_use_id, f"{name} non è riuscito: {detail}", True)
        if isinstance(value, list):
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": value}
        text = json.dumps(value, ensure_ascii=False)
        if tool.effect:
            ctx.ledger.record_operation(operation_id, ctx.instance, name, text)
        return self._result(tool_use_id, text, False)

    def _restore(self, name: str, stored: str) -> None:
        """Alla ripresa, uno strumento di chiusura già eseguito chiude di nuovo con lo stesso esito."""
        if name in CLOSE_ALWAYS:
            self.context.finished = Outcome(state=CLOSE_ALWAYS[name], note="ripreso dopo un'interruzione")
        elif name == "select_concepts":
            chosen = SelectConcepts.model_validate_json(stored).chosen
            state = OutcomeState.SELECTED if chosen else OutcomeState.NO_CONCEPT
            self.context.finished = Outcome(state=state, note=stored)
        elif name == "draft_presentation" and "pagine" not in json.loads(stored):  # nessuna proposta regge
            self.context.finished = Outcome(state=OutcomeState.NO_CONCEPT, note=stored)
        elif name == "present_concepts":
            proposals = PresentConcepts.model_validate_json(stored).proposals
            state = OutcomeState.PRESENTED if proposals else OutcomeState.NO_CONCEPT
            self.context.finished = Outcome(state=state, note=stored)

    @staticmethod
    def _result(tool_use_id: str, text: str, is_error: bool) -> dict:
        block: dict = {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}
        if is_error:
            block["is_error"] = True
        return block
