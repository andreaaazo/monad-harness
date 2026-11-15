"""The agent tools on the project's files: read, list, write, skills and images."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError
from pydantic import Field

from agency import registry
from agency.contracts.media import media_type, open_image
from agency.toolkit.base import Refused, Strict, Tool, ToolContext, viewed
from agency.workshop import craft
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    clip,
    ensure_dir_under,
    inside,
    open_under,
    read_under,
    replace_under,
)

TEXT_FILES = (".md", ".txt", ".json")


IMAGE_SIDE = 1600


IMAGE_BYTES = 3_500_000


IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


# The harness's folders in /job, which list_files does not show. `.ops` held its files before ADR-0044 and can
# still be in an older work folder.
HIDDEN = frozenset({".ops", craft.PARTIAL})


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


def _text_only(path: str) -> None:
    if not path.lower().endswith(TEXT_FILES):
        raise Refused(f"{path}: con write_file solo note di testo. I vettori stanno nel master.")


def read_file(ctx: ToolContext, a: ReadFile, _: str) -> dict:
    target = inside(ctx.work, a.path)
    if not target.is_file():
        raise Refused(f"{a.path}: non esiste")
    lines = read_under(ctx.work, a.path, MAX_TEXT_FILE_BYTES).decode("utf-8", errors="replace").splitlines()
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
    if ctx.actor in registry.REVIEWERS and not a.path.startswith("reviews/"):
        raise Refused("un revisore scrive solo in reviews/: non modifica il lavoro che giudica")
    folder = PurePosixPath(a.path).parent
    if folder.parts:
        ensure_dir_under(ctx.work, str(folder))
    replace_under(ctx.work, a.path, a.content.encode("utf-8"))
    return {"ok": True, "path": a.path}


def read_skill(_: ToolContext, a: ReadSkill, __: str) -> dict:
    if a.name != "org" and a.name not in registry.skill_names():
        raise Refused(f"skill sconosciuta: {a.name}. Disponibili: {registry.skills_index()}")
    root = registry.PROMPTS / ("org" if a.name == "org" else f"skills/{a.name}")
    target = inside(root, a.file)
    if not target.is_file():
        raise Refused(f"{a.file}: non esiste in {a.name}")
    return {"text": target.read_text(encoding="utf-8")}


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
    seen = viewed(ctx)
    try:
        image = open_image(raw)
    except UnidentifiedImageError as exc:
        raise Refused(f"{a.path}: non è un'immagine leggibile. Usa render.") from exc
    ctx.ledger.record_operation(operation_id, ctx.instance, "view_image", json.dumps({"key": key}))
    with image:
        media = media_type(image)
        size = image.size
        reduce = max(size) > IMAGE_SIDE or len(raw) > IMAGE_BYTES
        if reduce:  # a large image is scaled down, not refused
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


TOOLS: tuple[Tool, ...] = (
    Tool("read_file", "Legge un file di testo del progetto.", ReadFile, read_file, effect=False),
    Tool("list_files", "Elenca i file del progetto.", ListFiles, list_files, effect=False),
    Tool("write_file", "Scrive una nota di testo.", WriteFile, write_file),
    Tool("read_skill", "Carica una skill o un documento dello studio.", ReadSkill, read_skill, effect=False),
    Tool("view_image", "Mostra un'immagine. Costa contesto.", ViewImage, view_image, effect=False),
)
