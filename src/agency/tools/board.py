"""The anonymous board: the same conditions for every idea, at a large size and at small ones."""

from __future__ import annotations

import hashlib
import io
import random
from pathlib import Path
from typing import cast

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from agency.contracts.media import open_image
from agency.tools.files import MAX_IMAGE_FILE_BYTES, ensure_dir_under, read_under, replace_under

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
LIGHT = 200  # a corner lighter than this is background; a darker one is the mark reaching the edge
INK = [0] * 11 + [255] * 245  # everything that stands out from the background
GRID = 160  # the side of the grid on which the ink groups are counted
REACH = 7  # joins what is closer than about 3%: the letters of a word stay one mark
MAIN_SHARE = 0.75  # the main mark spans at least this share of the inked area's longer side


def assign_letters(project: str, round_: int, letters: list[str]) -> dict[str, str]:
    """A stable shuffle: the anonymous letter does not give the explorer away, and a resume keeps it."""
    seed = int(hashlib.sha256(f"{project}:{round_}".encode()).hexdigest()[:12], 16)
    shuffled = list(ANON[-len(letters) :])
    random.Random(seed).shuffle(shuffled)
    return dict(zip(letters, shuffled, strict=True))


def _open(path: Path) -> Image.Image:
    return open_image(read_under(ROOT, str(path.relative_to(ROOT)), MAX_IMAGE_FILE_BYTES))


def _flat(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (*WHITE, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB")


def _mask(rgb: Image.Image) -> Image.Image:
    """What stands out from the background. A uniform light ground is background, not part of the mark."""
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
    """Crops to the mark and removes the ground, so every sketch is seen in the same conditions."""
    rgb = _flat(image)
    mask = _mask(rgb)
    box = mask.getbbox()
    if box is None:
        return rgb
    clean = Image.new("RGB", rgb.size, WHITE)
    clean.paste(rgb, mask=mask)
    return clean.crop(box)


def _groups(mask: Image.Image) -> list[int]:
    """The longer side of each separate ink group, on a reduced grid."""
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
    """The board scales the whole inked area down at once: several marks side by side would look smaller
    than the others. The share is measured on the inked area's longer side, not on the file.

    It is an estimate: a word with separate letters can look like several marks. That is why whoever gets the
    warning can deliver the same file again: a mistake costs one call, and never blocks the work.
    """
    with _open(path) as image:
        sides = _groups(_mask(_flat(image)))
    if len(sides) < 2 or max(sides) / GRID >= MAIN_SHARE:
        return None
    return (
        f"il file sembra contenere {len(sides)} segni separati, e il maggiore occupa solo il "
        f"{max(sides) / GRID:.0%} del lato più lungo del disegno. La tavola lo rimpicciolisce tutto "
        "insieme, quindi verrebbe giudicato più piccolo degli altri. Lascia un solo segno, senza varianti "
        "né riduzioni: quelle stanno nel foglio. Se è davvero un solo segno in più parti, consegnalo di "
        "nuovo così com'è."
    )


def build(items: list[tuple[str, Path]], output: Path) -> None:
    """The board: each sketch under its anonymous letter, cropped to its mark, large and at `SMALL` sizes."""
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
