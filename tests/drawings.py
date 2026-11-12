"""Test drawings for the blind-judgment board (ADR-0041): an SVG with a single rectangle, and a fake
renderer.

The real renderer is vectorcraft-cli. These tests do not depend on the machine: the fake understands only
the canvas and the rectangle, and renders them like `vectorcraft-cli convert --scale`, with the rest
transparent. The test with the real one is skipped when it is missing.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

INK = (17, 17, 19, 255)


def svg(canvas: tuple[float, float], rect: tuple[float, float, float, float]) -> str:
    """A canvas and a rectangle, with a title the board must not show."""
    width, height = canvas
    x, y, w, h = rect
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><title>origine</title>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#111113"/></svg>'
    )


def red_pixels(image: Image.Image) -> int:
    """How many pixels are clearly red: the colour of the secret images the sandbox tests try to draw."""
    data = image.convert("RGB").tobytes()
    return sum(1 for i in range(0, len(data), 3) if data[i] > 150 and data[i + 1] < 60 and data[i + 2] < 60)


def _numbers(text: str, tag: str) -> dict[str, float]:
    element = re.search(rf"<{tag}\b[^>]*>", text)
    assert element is not None, tag
    return {name: float(value) for name, value in re.findall(r'([\w-]+)="([\d.]+)"', element[0])}


class FakeVectorcraft:
    """Notes the scale of each rendering: the small sizes are rendered at their own, not reduced."""

    def __init__(self) -> None:
        self.scales: list[float] = []

    def __call__(self, source: Path, scale: float, target: Path) -> None:
        self.scales.append(scale)
        text = source.read_text(encoding="utf-8")
        canvas, rect = _numbers(text, "svg"), _numbers(text, "rect")
        size = (max(1, round(canvas["width"] * scale)), max(1, round(canvas["height"] * scale)))
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        if rect["width"] and rect["height"]:
            # Like a real renderer, a drawing smaller than a pixel still leaves one pixel.
            left, top = round(rect["x"] * scale), round(rect["y"] * scale)
            right = max(left, round((rect["x"] + rect["width"]) * scale) - 1)
            bottom = max(top, round((rect["y"] + rect["height"]) * scale) - 1)
            ImageDraw.Draw(image).rectangle((left, top, right, bottom), fill=INK)
        image.save(target, format="PNG")
