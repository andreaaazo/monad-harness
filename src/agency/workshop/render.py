"""Renders an output into an image to look at, and records which version was rendered."""

from __future__ import annotations

import io
from pathlib import Path, PurePosixPath

from PIL import Image

from agency.contracts.ledger import Proofs
from agency.contracts.media import open_image
from agency.workshop.files import (
    MAX_IMAGE_FILE_BYTES,
    ensure_dir_under,
    inside,
    read_under,
    replace_under,
    sha256_under,
)
from agency.workshop.sandbox import JOB, Sandbox

DEFAULT_SIZE = 1200
PROOFS = "proofs/render"
VECTORS = (".svg", ".vectorcraft")
IMAGES = (".png", ".jpg", ".jpeg", ".webp")
RENDERABLE = (*VECTORS, *IMAGES)


def proof_stem(relative: str) -> str:
    return relative.replace("/", "_")


def _open(work: Path, relative: str) -> Image.Image:
    return open_image(read_under(work, relative, MAX_IMAGE_FILE_BYTES))


def _save(image: Image.Image, work: Path, relative: str) -> None:
    """Encodes by the name's suffix, as `Image.save` does, then replaces the file without following it."""
    buffer = io.BytesIO()
    image.save(buffer, format=Image.registered_extensions().get(PurePosixPath(relative).suffix.lower()))
    replace_under(work, relative, buffer.getvalue())


def render_one(
    sandbox: Sandbox,
    ledger: Proofs,
    project: str,
    relative: str,
    zooms: list[tuple[float, float, float, float]] | None = None,
) -> list[str]:
    """Renders the file to a PNG proof, plus one crop per zoom box (fractions of the width and height), and
    records which version of the file they show. Returns the proofs' paths."""
    source = inside(sandbox.work, relative)
    if not source.exists():
        raise FileNotFoundError(relative)
    ensure_dir_under(sandbox.work, PROOFS)
    proof = f"{PROOFS}/{proof_stem(relative)}.png"
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
    # A white ground: otherwise a black mark on transparency cannot be seen.
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
        zoom_path = f"{PROOFS}/{proof_stem(relative)}_zoom_{x:.2f}_{y:.2f}_{w:.2f}_{h:.2f}.png"
        _save(crop, sandbox.work, zoom_path)
        proofs.append(zoom_path)
    flat.thumbnail((DEFAULT_SIZE, DEFAULT_SIZE))
    _save(flat, sandbox.work, proof)
    ledger.add_render(project, relative, sha256_under(sandbox.work, relative), proofs)
    return proofs


__all__ = ["DEFAULT_SIZE", "proof_stem", "render_one"]
