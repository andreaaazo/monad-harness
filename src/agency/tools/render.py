"""Rende un output in un'immagine da guardare e registra quale versione è stata resa."""

from __future__ import annotations

import io
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw

from agency.ledger import Ledger
from agency.tools.files import ensure_dir_under, inside, read_under, replace_under, sha256_under
from agency.tools.sandbox import JOB, Sandbox

DEFAULT_SIZE = 1200
PROOFS = "proofs/render"
VECTORS = (".svg", ".vectorcraft")
IMAGES = (".png", ".jpg", ".jpeg", ".webp")
RENDERABLE = (*VECTORS, *IMAGES)


def _stem(relative: str) -> str:
    return relative.replace("/", "_").rsplit(".", 1)[0]


def _open(work: Path, relative: str) -> Image.Image:
    return Image.open(io.BytesIO(read_under(work, relative)))


def _save(image: Image.Image, work: Path, relative: str) -> None:
    """Encodes by the name's suffix, as `Image.save` does, then replaces the file without following it."""
    buffer = io.BytesIO()
    image.save(buffer, format=Image.registered_extensions().get(PurePosixPath(relative).suffix.lower()))
    replace_under(work, relative, buffer.getvalue())


def render_one(
    sandbox: Sandbox,
    ledger: Ledger,
    project: str,
    relative: str,
    zooms: list[tuple[float, float, float, float]] | None = None,
) -> list[str]:
    source = inside(sandbox.work, relative)
    if not source.exists():
        raise FileNotFoundError(relative)
    ensure_dir_under(sandbox.work, PROOFS)
    proof = f"{PROOFS}/{_stem(relative)}.png"
    extension = source.suffix.lower()
    if extension in VECTORS:
        done = sandbox.run(
            ["vectorcraft-cli", "convert", f"{JOB}/{relative}", f"{JOB}/{proof}", "--scale", "3"]
        )
        if done.code:
            raise RuntimeError(done.output.strip()[:300])
    elif extension in IMAGES:
        with _open(sandbox.work, relative) as image:
            _save(image.convert("RGBA"), sandbox.work, proof)
    else:
        raise ValueError(f"{extension}: render non disponibile in M1")
    with _open(sandbox.work, proof) as image:
        full = image.convert("RGBA")
    # Fondo bianco: un segno nero su trasparenza altrimenti non si vede.
    canvas = Image.new("RGBA", full.size, (255, 255, 255, 255))
    canvas.alpha_composite(full)
    flat = canvas.convert("RGB")
    proofs = [proof]
    for x, y, w, h in zooms or []:
        box = (
            int(x * flat.width),
            int(y * flat.height),
            int((x + w) * flat.width),
            int((y + h) * flat.height),
        )
        crop = flat.crop(box)
        crop.thumbnail((DEFAULT_SIZE, DEFAULT_SIZE))
        zoom_path = f"{PROOFS}/{_stem(relative)}_zoom_{x:.2f}_{y:.2f}.png"
        _save(crop, sandbox.work, zoom_path)
        proofs.append(zoom_path)
    flat.thumbnail((DEFAULT_SIZE, DEFAULT_SIZE))
    _save(flat, sandbox.work, proof)
    ledger.add_render(project, relative, sha256_under(sandbox.work, relative), proofs)
    return proofs


def contact_sheet(sandbox: Sandbox, images: list[str], output: str, cell: int = 300) -> str:
    columns = 4
    rows = (len(images) + columns - 1) // columns
    board = Image.new("RGB", (columns * cell, rows * (cell + 22)), (240, 240, 240))
    for position, relative in enumerate(images):
        with _open(sandbox.work, relative) as image:
            thumb = image.convert("RGB")
        thumb.thumbnail((cell, cell))
        tile = Image.new("RGB", (cell, cell + 22), (255, 255, 255))
        tile.paste(thumb, ((cell - thumb.width) // 2, (cell - thumb.height) // 2))
        ImageDraw.Draw(tile).text((6, cell + 5), Path(relative).stem[-44:], fill=(40, 40, 40))
        board.paste(tile, ((position % columns) * cell, (position // columns) * (cell + 22)))
    folder = PurePosixPath(output).parent
    if folder.parts:
        ensure_dir_under(sandbox.work, str(folder))
    _save(board, sandbox.work, output)
    return output


__all__ = ["DEFAULT_SIZE", "contact_sheet", "render_one"]
