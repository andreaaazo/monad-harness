"""La presentazione al cliente: ogni proposta in più pagine, poi la raccomandazione.

È un documento da leggere senza lo studio accanto. Il cliente non vede mai schizzi: vede proposte pulite,
nel contesto in cui vivranno, con il ragionamento e la raccomandazione. Il testo scorre sulle pagine che
servono: nessuna riga può uscire dal foglio, e il direttore guarda le pagine prima che arrivino al cliente.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1600, 1000
MARGIN = 60
BOTTOM = HEIGHT - MARGIN
INK = (20, 20, 20)
SOFT = (110, 110, 110)
PAPER = (255, 255, 255)
LEADING = 1.4
LABEL, TITLE, BODY = 24, 44, 28
TOP = 150  # dove comincia il contenuto, sotto etichetta e titolo
MARK_WIDTH = 760
COLUMN = 660  # testo accanto al segno
MEASURE = 1100  # testo a piena pagina: oltre questa misura le righe si leggono male


@lru_cache
def _font_file() -> str:
    """Un font di sistema con gli accenti: quello predefinito di Pillow non ha è, ì, ù."""
    for family in ("Noto Sans", "DejaVu Sans"):
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", family], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        if found.lower().endswith((".ttf", ".otf")):
            return found
    raise FileNotFoundError("nessun font con gli accenti: installa fonts-noto-core")


@lru_cache
def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_file(), size)


@dataclass(frozen=True)
class Proposal:
    letter: str
    title: str
    idea: str
    why: str
    risk: str
    mark: Path
    applications: tuple[Path, ...]


def _fit(path: Path, box: tuple[int, int]) -> Image.Image:
    with Image.open(path) as image:
        flat = Image.new("RGBA", image.size, (255, 255, 255, 255))
        flat.alpha_composite(image.convert("RGBA"))
    picture = flat.convert("RGB")
    picture.thumbnail(box, Image.Resampling.LANCZOS)
    return picture


def wrap(text: str, size: int, width: int) -> list[str]:
    """A capo sulla larghezza reale: una parola troppo lunga si spezza invece di uscire dal foglio."""
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
    text: str
    heading: str = ""
    size: int = BODY


@dataclass(frozen=True)
class Line:
    text: str
    y: int
    size: int
    fill: tuple[int, int, int]


def flow(blocks: list[Block], width: int, height: int, first: int = 0) -> list[list[Line]]:
    """Distribuisce il testo in colonne alte `height` (la prima alta `first`): non si perde nessuna parola."""
    columns: list[list[Line]] = [[]]
    y = 0
    limit = first or height

    def place(text: str, size: int, fill: tuple[int, int, int], keep: int = 1) -> None:
        nonlocal y, limit
        step = int(size * LEADING)
        if y + step * keep > limit and columns[-1]:  # un titolo non resta solo in fondo alla colonna
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
    """La proposta a colpo d'occhio, per il direttore: una sola immagine da guardare."""
    page = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    picture = _fit(mark, (640, 760))
    page.paste(picture, (MARGIN + (640 - picture.width) // 2, 120 + (760 - picture.height) // 2))
    _grid(page, applications, 760, 60, 780, 880)
    output.parent.mkdir(parents=True, exist_ok=True)
    page.save(output)


def _page(label: str, title: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    """Una pagina con etichetta e titolo: restituisce dove comincia il contenuto."""
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
    """La cartella della presentazione di un giro, relativa a work/."""
    return f"presentation/r{turn}"


def pdf_of(turn: int) -> str:
    """Il file che il cliente riceve, relativo a work/."""
    return f"{folder_of(turn)}/{PDF}"


def proposal_files(work: Path, turn: int, anon: str) -> tuple[Path, tuple[Path, ...]]:
    letter = anon.lower()
    folder = work / f"proposals/r{turn}/{letter}"
    return folder / f"proposta-{letter}.png", tuple(sorted((folder / f"applicazioni-{letter}").glob("*.png")))


def build(proposals: list[Proposal], recommended: str, reasons: str, folder: Path) -> list[Path]:
    """Scrive il PDF e un'immagine per ogni pagina: sono quelle che il direttore deve guardare."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("pagina-*.png"):  # una bozza più corta non lascia pagine vecchie
        old.unlink()
    pages = [page for item in proposals for page in _proposal_pages(item)]
    pages += _closing_pages(recommended, reasons)
    files = []
    for number, page in enumerate(pages, start=1):
        files.append(folder / f"pagina-{number}.png")
        page.save(files[-1])
    pages[0].save(folder / PDF, save_all=True, append_images=pages[1:])
    return files
