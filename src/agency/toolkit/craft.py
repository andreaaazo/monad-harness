"""The agent tools that build: Craft commands, isolated computation, renders and exports from the master."""

from __future__ import annotations

from pydantic import Field

from agency.contracts.project import parse_project_name
from agency.contracts.sandbox import OPS
from agency.toolkit.base import Refused, Strict, Tool, ToolContext
from agency.workshop import craft, master, render
from agency.workshop.files import clip, replace_under

EXPORT_OPTIONS = {"--artboard", "--range", "--scale", "--outline-text", "--decimals"}


NO_OPS = "{tool} non è disponibile in questa sandbox: manca la cartella /ops"


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


def render_tool(ctx: ToolContext, a: Render, _: str) -> dict:
    zooms = [(z[0], z[1], z[2], z[3]) for z in a.zooms]
    return {"proofs": render.render_one(ctx.sandbox, ctx.ledger, ctx.project, a.path, zooms)}


CRAFT_APP = "vectorcraft"  # every craft tool drives VectorCraft in this phase


def require_craft_app(ctx: ToolContext, app: str = CRAFT_APP) -> None:
    if app not in ctx.rules.roles[ctx.actor].craft:
        raise Refused(f"{ctx.actor} non lavora con {app}")


def craft_search(ctx: ToolContext, a: CraftSearch, _: str) -> dict:
    require_craft_app(ctx)
    return {"commands": [{"id": c.id, "label": c.label} for c in ctx.index.search(a.query)]}


def craft_describe(ctx: ToolContext, a: CraftDescribe, _: str) -> dict:
    require_craft_app(ctx)
    command = ctx.index.commands.get(a.command)
    if command is None:
        raise Refused(f"comando inesistente: {a.command}. Usa craft_search.")
    return {"id": command.id, "label": command.label, "params": command.params}


def craft_run(ctx: ToolContext, a: CraftRun, operation_id: str) -> dict:
    require_craft_app(ctx)
    if not a.document.endswith(".vectorcraft"):
        raise Refused("in questa fase craft_run lavora su documenti .vectorcraft")
    outputs = ctx.finisher_outputs
    if outputs and a.document not in outputs:
        raise Refused("il concetto è scelto: lavori solo sui master in OUTPUT, niente file di esplorazione")
    safe = "".join(c if c.isalnum() else "_" for c in operation_id)
    if ctx.sandbox.ops is None or ctx.settings is None:
        raise Refused(NO_OPS.format(tool="craft_run"))
    records = ctx.settings.layout.ops_records(parse_project_name(ctx.project), ctx.instance)
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


TOOLS: tuple[Tool, ...] = (
    Tool("render", "Rende un SVG, un master o un'immagine in PNG da guardare.", Render, render_tool),
    Tool("craft_search", "Cerca nei comandi di VectorCraft.", CraftSearch, craft_search, effect=False),
    Tool("craft_describe", "Mostra i parametri di un comando.", CraftDescribe, craft_describe, effect=False),
    Tool("craft_run", "Esegue passi su un master VectorCraft.", CraftRun, craft_run),
    Tool("compute", "Esegue Python isolato per calcolare geometria e misure.", Compute, compute),
    Tool("export_master", "Esporta dal master e registra il legame.", ExportMaster, export_master),
)
