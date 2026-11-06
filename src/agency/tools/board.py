"""La tavola anonima: stesse condizioni per tutte le idee, a misura grande e piccola."""

from __future__ import annotations

import hashlib
import io
import random
from pathlib import Path
from typing import cast

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from agency.tools.files import ensure_dir_under, read_under, replace_under

# The callers pass absolute paths under a work folder they resolved, so no component may be a link: each
# file is reached from the filesystem root through the no-follow helpers.
ROOT = Path("/")

CELL = 480
MARGIN = 30
ANON = "VWXYZ"
COLUMNS = 3
ROW = CELL + 180
SMALL = (96, 48, 24)
WHITE = (255, 255, 255)
LIGHT = 200  # un angolo più chiaro di così è sfondo; più scuro è il segno che arriva al bordo
INK = [0] * 11 + [255] * 245  # tutto ciò che si stacca dallo sfondo
GRID = 160  # lato su cui si contano i gruppi di inchiostro
REACH = 7  # raggruppa ciò che dista meno del 3% circa: le lettere di una parola restano un solo segno
MAIN_SHARE = 0.75  # il segno principale occupa almeno questa parte del file


def assign_letters(project: str, round_: int, letters: list[str]) -> dict[str, str]:
    """Rimescola in modo stabile: la lettera anonima non rivela l'esploratore, e la ripresa non la cambia."""
    seed = int(hashlib.sha256(f"{project}:{round_}".encode()).hexdigest()[:12], 16)
    shuffled = list(ANON[-len(letters) :])
    random.Random(seed).shuffle(shuffled)
    return dict(zip(letters, shuffled, strict=True))


def _open(path: Path) -> Image.Image:
    return Image.open(io.BytesIO(read_under(ROOT, str(path.relative_to(ROOT)))))


def _flat(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (*WHITE, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB")


def _mask(rgb: Image.Image) -> Image.Image:
    """Ciò che si stacca dallo sfondo. Un fondo chiaro uniforme è sfondo, non parte del segno."""
    right, bottom = rgb.width - 1, rgb.height - 1
    corners = {rgb.getpixel(point) for point in ((0, 0), (right, 0), (0, bottom), (right, bottom))}
    background = WHITE
    if len(corners) == 1:
        corner = cast("tuple[int, int, int]", corners.pop())
        if sum(corner) / 3 >= LIGHT:
            background = corner
    distance = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background))
    return distance.convert("L").point(INK)


def _ink(image: Image.Image) -> Image.Image:
    """Ritaglia sul segno e toglie il fondo: tutti gli schizzi si vedono nelle stesse condizioni."""
    rgb = _flat(image)
    mask = _mask(rgb)
    box = mask.getbbox()
    if box is None:
        return rgb
    clean = Image.new("RGB", rgb.size, WHITE)
    clean.paste(rgb, mask=mask)
    return clean.crop(box)


def _groups(mask: Image.Image) -> list[int]:
    """Il lato maggiore di ogni gruppo di inchiostro separato, su una griglia ridotta."""
    box = mask.getbbox()
    if box is None:
        return []
    crop = mask.crop(box)
    scale = GRID / max(crop.size)
    size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    small = crop.resize(size, Image.Resampling.BOX).point([0] + [255] * 255)
    grown = small.filter(ImageFilter.MaxFilter(REACH))
    width, height = grown.size
    cells = grown.tobytes()
    seen = bytearray(width * height)
    sides = []
    for start in range(width * height):
        if seen[start] or not cells[start]:
            continue
        seen[start] = 1
        stack = [start]
        left, right, top, bottom = width, 0, height, 0
        while stack:
            cell = stack.pop()
            y, x = divmod(cell, width)
            left, right, top, bottom = min(left, x), max(right, x), min(top, y), max(bottom, y)
            near = (
                [cell - width, cell + width]
                + ([cell - 1] if x else [])
                + ([cell + 1] if x < width - 1 else [])
            )
            for other in near:
                if 0 <= other < width * height and cells[other] and not seen[other]:
                    seen[other] = 1
                    stack.append(other)
        sides.append(max(right - left, bottom - top) + 1)
    return sides


def mark_problem(path: Path) -> str | None:
    """La tavola rimpicciolisce tutto il file: più segni insieme sembrerebbero più piccoli degli altri.

    È una stima: una parola a lettere staccate può sembrare più segni. Per questo chi riceve l'avviso può
    riconsegnare lo stesso file: sbagliare costa una chiamata, non blocca mai il lavoro.
    """
    with _open(path) as image:
        sides = _groups(_mask(_flat(image)))
    if len(sides) < 2 or max(sides) / GRID >= MAIN_SHARE:
        return None
    return (
        f"il file sembra contenere {len(sides)} segni separati, e il maggiore occupa solo il "
        f"{max(sides) / GRID:.0%} della larghezza. La tavola lo rimpicciolisce tutto insieme, quindi "
        "verrebbe giudicato più piccolo degli altri. Lascia un solo segno, senza varianti né riduzioni: "
        "quelle stanno nel foglio. Se è davvero un solo segno in più parti, consegnalo di nuovo così com'è."
    )


def build(items: list[tuple[str, Path]], output: Path) -> None:
    columns = min(len(items), COLUMNS)
    rows = (len(items) + COLUMNS - 1) // COLUMNS
    width = columns * (CELL + MARGIN) + MARGIN
    board = Image.new("RGB", (width, rows * ROW), (255, 255, 255))
    draw = ImageDraw.Draw(board)
    for position, (anon, path) in enumerate(sorted(items)):
        left = MARGIN + (position % COLUMNS) * (CELL + MARGIN)
        top = (position // COLUMNS) * ROW
        with _open(path) as image:
            mark = _ink(image)
        big = mark.copy()
        big.thumbnail((CELL - 60, CELL - 60), Image.Resampling.LANCZOS)
        scale = (CELL - 60) / max(big.size)
        if scale > 1:
            size = (int(big.width * scale), int(big.height * scale))
            big = mark.resize(size, Image.Resampling.LANCZOS)
        board.paste(big, (left + (CELL - big.width) // 2, top + 40 + (CELL - big.height) // 2))
        draw.text((left, top + 8), anon, fill=(0, 0, 0), font_size=26)
        x = left
        for side in SMALL:
            tiny = mark.copy()
            tiny.thumbnail((side, side), Image.Resampling.LANCZOS)
            board.paste(tiny, (x, top + CELL + 60))
            x += side + 40
    ensure_dir_under(ROOT, str(output.parent.relative_to(ROOT)))
    buffer = io.BytesIO()
    board.save(buffer, format=Image.registered_extensions().get(output.suffix.lower()))
    replace_under(ROOT, str(output.relative_to(ROOT)), buffer.getvalue())
