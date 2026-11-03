"""Disegni di prova per la tavola del giudizio (ADR-0041): un SVG con un rettangolo solo, e un renderer finto.

Il renderer vero è vectorcraft-cli. Queste prove non dipendono dalla macchina: il finto capisce solo
la tela e il rettangolo, e li rende come `vectorcraft-cli convert --scale`, con il resto trasparente.
La prova con quello vero si salta se manca.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

INK = (17, 17, 19, 255)


def svg(canvas: tuple[float, float], rect: tuple[float, float, float, float]) -> str:
    """Una tela e un rettangolo, con un titolo che la tavola non deve mostrare."""
    width, height = canvas
    x, y, w, h = rect
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><title>origine</title>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#111113"/></svg>'
    )


def _numbers(text: str, tag: str) -> dict[str, float]:
    element = re.search(rf"<{tag}\b[^>]*>", text)
    assert element is not None, tag
    return {name: float(value) for name, value in re.findall(r'([\w-]+)="([\d.]+)"', element[0])}


class FakeVectorcraft:
    """Annota la scala di ogni rendering: le misure piccole si rendono alla loro, non si riducono."""

    def __init__(self) -> None:
        self.scales: list[float] = []

    def __call__(self, source: Path, scale: float, target: Path) -> None:
        self.scales.append(scale)
        text = source.read_text(encoding="utf-8")
        canvas, rect = _numbers(text, "svg"), _numbers(text, "rect")
        size = (max(1, round(canvas["width"] * scale)), max(1, round(canvas["height"] * scale)))
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        if rect["width"] and rect["height"]:
            # Come un renderer vero, un disegno più piccolo di un pixel lascia comunque un pixel.
            left, top = round(rect["x"] * scale), round(rect["y"] * scale)
            right = max(left, round((rect["x"] + rect["width"]) * scale) - 1)
            bottom = max(top, round((rect["y"] + rect["height"]) * scale) - 1)
            ImageDraw.Draw(image).rectangle((left, top, right, bottom), fill=INK)
        image.save(target, format="PNG")
