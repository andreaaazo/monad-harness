"""La tavola del giudizio alla cieca: ogni disegno alla stessa misura, grande e alle misure d'uso (ADR-0041).

Aperti da soli, due file non sono alla pari. Un browser mostra un SVG alla misura scritta nel file,
98 px l'uno e 800 l'altro, e il suo titolo nella scheda. Anche nello stesso riquadro, un disegno che
riempie meno la sua tela sembra più piccolo. La tavola misura il disegno, non la tela: ogni lettera ha
lo stesso quadrato su fondo bianco, e il lato più lungo del disegno è uguale per tutte. Le misure
piccole si rendono ciascuna alla sua scala, come in `logo_proof`, e non si riducono da un'immagine grande.
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

LARGE = 480  # il lato più lungo del disegno grande, in px
SMALL = (64, 32, 16)
SIZES = (LARGE, *SMALL)
MARGIN = 40
CELL = LARGE + 2 * MARGIN  # il quadrato di ogni lettera
STRIP = max(SMALL) + MARGIN // 2  # la riga delle misure piccole
LABEL = 56
ROW = CELL + STRIP + LABEL
COLUMNS = 3
SPACING = 32  # tra le misure piccole
MEASURE = 1024  # il lato più lungo della tela quando si misura il disegno
LIMIT = 16384  # oltre questo lato la tela da rendere sarebbe enorme: il disegno ne occupa una parte minima
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
    """La tavola accanto alle copie anonime, o None per un tipo di file che non ne ha una.

    Si disegna dalle copie, che hanno l'hash letto all'inizio: la tavola mostra esattamente ciò che
    si giudica. I rendering intermedi stanno nella cartella anonima, e se ne vanno prima delle domande.
    """
    if {copy.suffix.lower() for copy in copies.values()} - KINDS:
        return None
    with tempfile.TemporaryDirectory(dir=folder) as scratch:
        drawings = {letter: drawn(copy, render, Path(scratch)) for letter, copy in copies.items()}
    target = folder / NAME
    compose(drawings).save(target, format="PNG")
    return target


def drawn(copy: Path, render: Render | None, scratch: Path) -> dict[int, Image.Image]:
    """Il disegno di un file a ogni misura della tavola, ritagliato: il lato più lungo è la misura."""
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
    drawing = max(box[2] - box[0], box[3] - box[1]) / scale  # in px della tela
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
    """Dove il disegno non è trasparente. Un raster senza trasparenza si misura sulla sua tela."""
    return image.getchannel("A").getbbox()


def _trim(image: Image.Image) -> Image.Image:
    """A una misura piccola un tratto sottile può sparire: resta un vuoto, che è ciò che si vedrebbe."""
    box = _box(image)
    return image.crop(box) if box else Image.new("RGBA", (1, 1))


def _fit(image: Image.Image, size: int) -> Image.Image:
    factor = size / max(image.size)
    fitted = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    return image.resize(fitted, Image.Resampling.LANCZOS)


def compose(drawings: Mapping[str, Mapping[int, Image.Image]]) -> Image.Image:
    """Le lettere in ordine, tre per riga: il quadrato grande, le misure piccole e la sola lettera."""
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
