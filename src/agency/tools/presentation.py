"""The presentation to the client: each proposal over several pages, then the recommendation.

It is a document to read without the studio beside it. The client never sees sketches: they see clean
proposals, in the context they will live in, with the reasoning and the recommendation. The text flows over
as many pages as it needs: no line can run off the page, and the director looks at the pages before they
reach the client.
"""

from __future__ import annotations

import fnmatch
import io
import os
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont

from agency.contracts.media import open_image
from agency.tools.files import MAX_IMAGE_FILE_BYTES, ensure_dir_under, open_under, read_under, replace_under

# The callers pass absolute paths under a work folder they resolved, so no component may be a link: `_fit`
# and `build` reach each file from the filesystem root through the no-follow helpers.
ROOT = Path("/")

WIDTH, HEIGHT = 1600, 1000
MARGIN = 60
BOTTOM = HEIGHT - MARGIN
INK = (20, 20, 20)
SOFT = (110, 110, 110)
PAPER = (255, 255, 255)
LEADING = 1.4
LABEL, TITLE, BODY = 24, 44, 28
TOP = 150  # where the content starts, below the label and the title
MARK_WIDTH = 760
COLUMN = 660  # text beside the mark
MEASURE = 1100  # full-page text: past this width the lines read badly


@lru_cache
def _font_file() -> str:
    """A system font that has the Italian accented letters, which Pillow's default font lacks."""
    for family in ("Noto Sans", "DejaVu Sans"):
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", family], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        if found.lower().endswith((".ttf", ".otf")):
            return found
    raise FileNotFoundError("nessun font con gli accenti: installa fonts-noto-core")


@lru_cache
def font(size: int) -> ImageFont.FreeTypeFont:
    """The presentation's font at `size` px."""
    return ImageFont.truetype(_font_file(), size)


@dataclass(frozen=True)
class Proposal:
    """One proposal as its pages show it: its texts, its mark and its applications."""

    letter: str
    title: str
    idea: str
    why: str
    risk: str
    mark: Path
    applications: tuple[Path, ...]


def _fit(path: Path, box: tuple[int, int]) -> Image.Image:
    with open_image(read_under(ROOT, str(path.relative_to(ROOT)), MAX_IMAGE_FILE_BYTES)) as image:
        flat = Image.new("RGBA", image.size, (255, 255, 255, 255))
        flat.alpha_composite(image.convert("RGBA"))
    picture = flat.convert("RGB")
    picture.thumbnail(box, Image.Resampling.LANCZOS)
    return picture


def wrap(text: str, size: int, width: int) -> list[str]:
    """Wraps at the real width: a word that is too long is broken instead of running off the page."""
    measure = font(size).getlength
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            while measure(word) > width:
                cut = len(word) - 1
                while cut > 1 and measure(word[:cut]) > width:
                    cut -= 1
                if line:
                    lines.append(line)
                    line = ""
                lines.append(word[:cut])
                word = word[cut:]
            candidate = f"{line} {word}".strip()
            if measure(candidate) > width:
                lines.append(line)
                candidate = word
            line = candidate
        if line:
            lines.append(line)
    return lines


@dataclass(frozen=True)
class Block:
    """A paragraph for `flow`, with an optional heading above it."""

    text: str
    heading: str = ""
    size: int = BODY


@dataclass(frozen=True)
class Line:
    """A placed line: its text, its offset from the column's top, its size and its colour."""

    text: str
    y: int
    size: int
    fill: tuple[int, int, int]


def flow(blocks: list[Block], width: int, height: int, first: int = 0) -> list[list[Line]]:
    """Spreads the text over columns `height` tall (the first one `first` tall): no word is lost."""
    columns: list[list[Line]] = [[]]
    y = 0
    limit = first or height

    def place(text: str, size: int, fill: tuple[int, int, int], keep: int = 1) -> None:
        nonlocal y, limit
        step = int(size * LEADING)
        if y + step * keep > limit and columns[-1]:  # a heading never stays alone at the foot of a column
            columns.append([])
            y = 0
            limit = height
        columns[-1].append(Line(text, y, size, fill))
        y += step

    for block in blocks:
        if block.heading:
            place(block.heading, LABEL, SOFT, keep=3)
        for line in wrap(block.text, block.size, width):
            place(line, block.size, INK)
        y += block.size
    return columns


def _write(draw: ImageDraw.ImageDraw, lines: list[Line], x: int, top: int) -> None:
    for line in lines:
        draw.text((x, top + line.y), line.text, fill=line.fill, font=font(line.size))


def _grid(page: Image.Image, images: tuple[Path, ...], left: int, top: int, width: int, height: int) -> None:
    if not images:
        return
    columns = 1 if len(images) == 1 else 2 if len(images) <= 4 else 3
    rows = (len(images) + columns - 1) // columns
    cell = (width // columns - 20, height // rows - 20)
    for position, path in enumerate(images):
        picture = _fit(path, cell)
        x = left + (position % columns) * (cell[0] + 20)
        y = top + (position // columns) * (cell[1] + 20)
        page.paste(picture, (x + (cell[0] - picture.width) // 2, y + (cell[1] - picture.height) // 2))


def sheet(mark: Path, applications: tuple[Path, ...], output: Path) -> None:
    """The proposal at a glance, for the director: a single image to look at."""
    page = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    picture = _fit(mark, (640, 760))
    page.paste(picture, (MARGIN + (640 - picture.width) // 2, 120 + (760 - picture.height) // 2))
    _grid(page, applications, 760, 60, 780, 880)
    ensure_dir_under(ROOT, str(output.parent.relative_to(ROOT)))
    replace_under(ROOT, str(output.relative_to(ROOT)), _encoded(page, "PNG"))


def _page(label: str, title: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    """A page with its label and title; returns where the content starts."""
    page = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(page)
    draw.text((MARGIN, 44), label, fill=SOFT, font=font(LABEL))
    y = 80
    for line in wrap(title, TITLE, WIDTH - 2 * MARGIN):
        draw.text((MARGIN, y), line, fill=INK, font=font(TITLE))
        y += int(TITLE * LEADING)
    return page, draw, max(y + 20, TOP)


def _text_pages(label: str, columns: list[list[Line]]) -> list[Image.Image]:
    pages = []
    for lines in columns:
        page, draw, top = _page(label)
        _write(draw, lines, MARGIN, top)
        pages.append(page)
    return pages


def _proposal_pages(proposal: Proposal) -> list[Image.Image]:
    label = f"Proposta {proposal.letter}"
    page, draw, top = _page(label, proposal.title)
    picture = _fit(proposal.mark, (MARK_WIDTH, BOTTOM - top))
    box_y = (BOTTOM - top - picture.height) // 2
    page.paste(picture, (MARGIN + (MARK_WIDTH - picture.width) // 2, top + box_y))
    columns = flow([Block(proposal.idea)], COLUMN, BOTTOM - TOP, first=BOTTOM - top)
    _write(draw, columns[0], WIDTH - MARGIN - COLUMN, top)
    pages = [page, *_text_pages(label, columns[1:])]
    if proposal.applications:
        page, _, top = _page(f"{label}: dove vive")
        _grid(page, proposal.applications, MARGIN, top, WIDTH - 2 * MARGIN, BOTTOM - top)
        pages.append(page)
    reasons = [Block(proposal.why, "Perché è giusta per voi"), Block(proposal.risk, "Il suo limite")]
    pages += _text_pages(label, flow(reasons, MEASURE, BOTTOM - TOP))
    return pages


def _closing_pages(recommended: str, reasons: str) -> list[Image.Image]:
    page, draw, top = _page("La nostra raccomandazione", f"Proposta {recommended}")
    columns = flow([Block(reasons)], MEASURE, BOTTOM - TOP, first=BOTTOM - top)
    _write(draw, columns[0], MARGIN, top)
    return [page, *_text_pages("La nostra raccomandazione", columns[1:])]


PDF = "presentazione.pdf"


def folder_of(turn: int) -> str:
    """The presentation folder of a round, relative to work/."""
    return f"presentation/r{turn}"


def pdf_of(turn: int) -> str:
    """The file the client receives, relative to work/."""
    return f"{folder_of(turn)}/{PDF}"


def proposal_files(
    work: Path, turn: int, anon: str, delivered: Iterable[str]
) -> tuple[Path, tuple[Path, ...]]:
    """The mark and the applications of a proposal. `delivered` holds paths relative to the proposal folder:
    only those are shown, so a file nobody delivered or checked never reaches the pages."""
    letter = anon.lower()
    folder = work / f"proposals/r{turn}/{letter}"
    shown = {
        folder / path
        for path in delivered
        if PurePosixPath(path).parent == PurePosixPath(f"applicazioni-{letter}") and path.endswith(".png")
    }
    return folder / f"proposta-{letter}.png", tuple(sorted(shown))


def _encoded(page: Image.Image, kind: str, **options: object) -> bytes:
    buffer = io.BytesIO()
    page.save(buffer, format=kind, **options)
    return buffer.getvalue()


def build(proposals: list[Proposal], recommended: str, reasons: str, folder: Path) -> list[Path]:
    """Writes the PDF and one image per page: those images are what the director must look at."""
    relative = str(folder.relative_to(ROOT))
    ensure_dir_under(ROOT, relative)
    directory = open_under(ROOT, relative, os.O_RDONLY | os.O_DIRECTORY)
    try:
        # a shorter draft leaves no old pages behind
        for old in fnmatch.filter(os.listdir(directory), "pagina-*.png"):
            os.unlink(old, dir_fd=directory)
    finally:
        os.close(directory)
    pages = [page for item in proposals for page in _proposal_pages(item)]
    pages += _closing_pages(recommended, reasons)
    files = []
    for number, page in enumerate(pages, start=1):
        files.append(folder / f"pagina-{number}.png")
        replace_under(ROOT, f"{relative}/pagina-{number}.png", _encoded(page, "PNG"))
    replace_under(
        ROOT, f"{relative}/{PDF}", _encoded(pages[0], "PDF", save_all=True, append_images=pages[1:])
    )
    return files
