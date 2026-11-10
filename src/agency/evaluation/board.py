"""The blind-judgment board: every drawing at the same size, large and at the sizes it is used at (ADR-0041).

Opened on their own, two files are not on equal terms. A browser shows an SVG at the size written in the
file, 98 px for one and 800 for the other, and its title in the tab. Even in the same frame, a drawing that
fills less of its canvas looks smaller. The board measures the drawing, not the canvas: each letter has the
same square on a white ground, and the drawing's longest side is the same for all. A vector's small sizes
are each rendered at their own scale, as in `logo_proof`, not reduced from a large image.
"""

from __future__ import annotations

import math
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from agency.contracts.files import MAX_IMAGE_FILE_BYTES, OutsidePerimeter, read_under
from agency.contracts.media import open_image
from agency.evaluation.blind import CannotCompare

LARGE = 480  # the large drawing's longest side, in px
SMALL = (64, 32, 16)
SIZES = (LARGE, *SMALL)
MARGIN = 40
CELL = LARGE + 2 * MARGIN  # each letter's square
STRIP = max(SMALL) + MARGIN // 2  # the row of small sizes
LABEL = 56
ROW = CELL + STRIP + LABEL
COLUMNS = 3
SPACING = 32  # between the small sizes
MEASURE = 1024  # the canvas's longest side when the drawing is measured
LIMIT = 16384  # past this side the canvas to render would be huge, the drawing a tiny part of it
TIMEOUT = 60
PAPER = (255, 255, 255)
INK = (60, 60, 64)
RULE = (228, 228, 230)
NAME = "tavola.png"
SHOWN = f"i disegni alla stessa misura, grandi e a {', '.join(map(str, SMALL[:-1]))} e {SMALL[-1]} px"
VECTOR = ".svg"
RASTER = frozenset({".png", ".jpg", ".jpeg", ".webp"})
KINDS = RASTER | {VECTOR}

type Render = Callable[[Path, float, Path], None]
type Box = tuple[int, int, int, int]


def lay_board(copies: Mapping[str, Path], folder: Path, render: Render | None) -> Path | None:
    """The board beside the anonymous copies, or None for a file type that has none.

    It is drawn from the copies, which have the hash read at the start, so the board shows exactly what is
    judged. The intermediate renderings stay in the anonymous folder and are gone before the questions.
    """
    if {copy.suffix.lower() for copy in copies.values()} - KINDS:
        return None
    with tempfile.TemporaryDirectory(dir=folder) as scratch:
        drawings = {letter: drawn(copy, render, Path(scratch)) for letter, copy in copies.items()}
    target = folder / NAME
    compose(drawings).save(target, format="PNG")
    return target


def drawn(copy: Path, render: Render | None, scratch: Path) -> dict[int, Image.Image]:
    """A file's drawing at each size of the board, trimmed: its longest side is the size."""
    if copy.suffix.lower() in RASTER:
        return _raster(copy)
    if render is None:
        raise CannotCompare(
            "vectorcraft-cli manca, e senza un renderer i disegni non si mostrano alla pari: "
            "agency doctor dice come averlo"
        )
    return _vector(copy, render, scratch)


def _vector(copy: Path, render: Render, scratch: Path) -> dict[int, Image.Image]:
    canvas = max(_rendered(render, copy, 1.0, scratch).size)
    scale = round(MEASURE / canvas, 6)
    box = _box(_rendered(render, copy, scale, scratch))
    if box is None:
        raise CannotCompare(f"{copy.name} non ha niente di disegnato")
    drawing = max(box[2] - box[0], box[3] - box[1]) / scale  # in canvas px
    if canvas * LARGE / drawing > LIMIT:
        raise CannotCompare(f"{copy.name}: il disegno occupa una parte troppo piccola della sua tela")
    sizes = {}
    for size in SIZES:
        image = _rendered(render, copy, round(size / drawing, 6), scratch)
        sizes[size] = _trim(image)
    return sizes


def _raster(copy: Path) -> dict[int, Image.Image]:
    try:
        with open_image(read_under(copy.parent, copy.name, MAX_IMAGE_FILE_BYTES)) as opened:
            image = opened.convert("RGBA")
    except (OSError, OutsidePerimeter, Image.DecompressionBombError) as exc:
        raise CannotCompare(f"{copy.name} non si apre come immagine: {exc}") from exc
    if _box(image) is None:
        raise CannotCompare(f"{copy.name} non ha niente di disegnato")
    drawing = _trim(image)
    return {size: _fit(drawing, size) for size in SIZES}


def _rendered(render: Render, copy: Path, scale: float, scratch: Path) -> Image.Image:
    target = scratch / f"{copy.stem}-{scale:.6f}.png"
    render(copy, scale, target)
    try:
        with open_image(target.read_bytes()) as opened:
            return opened.convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        raise CannotCompare(f"il rendering di {copy.name} non si legge: {exc}") from exc


def _box(image: Image.Image) -> Box | None:
    """Where the drawing is not transparent. A raster without transparency is measured on its canvas."""
    return image.getchannel("A").getbbox()


def _trim(image: Image.Image) -> Image.Image:
    """Crops to the drawing. At a small size a thin stroke can vanish: a blank is left, which is what one
    would see."""
    box = _box(image)
    return image.crop(box) if box else Image.new("RGBA", (1, 1))


def _fit(image: Image.Image, size: int) -> Image.Image:
    factor = size / max(image.size)
    fitted = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    return image.resize(fitted, Image.Resampling.LANCZOS)


def compose(drawings: Mapping[str, Mapping[int, Image.Image]]) -> Image.Image:
    """The letters in order, three per row: the large square, the small sizes, and the letter alone."""
    columns = min(len(drawings), COLUMNS)
    sheet = Image.new("RGB", (columns * CELL, math.ceil(len(drawings) / columns) * ROW), PAPER)
    pen = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=28)
    small = sum(SMALL) + SPACING * (len(SMALL) - 1)
    for index, (letter, sizes) in enumerate(drawings.items()):
        left, top = (index % columns) * CELL, (index // columns) * ROW
        _centre(sheet, sizes[LARGE], (left, top, CELL, CELL))
        x = left + (CELL - small) // 2
        for size in SMALL:
            _centre(sheet, sizes[size], (x, top + CELL, size, max(SMALL)))
            x += size + SPACING
        middle = (left + CELL // 2, top + CELL + STRIP + LABEL // 2)
        pen.text(middle, letter, fill=INK, font=font, anchor="mm")
        if index % columns:
            pen.line([(left, top), (left, top + ROW - 1)], fill=RULE)
    return sheet


def _centre(sheet: Image.Image, image: Image.Image, area: Box) -> None:
    left, top, width, height = area
    sheet.paste(image, (left + (width - image.width) // 2, top + (height - image.height) // 2), image)
