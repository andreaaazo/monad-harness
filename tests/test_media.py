"""Sandbox-written images are opened only as PNG, JPEG, WebP or GIF, and are labelled by their content."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import EpsImagePlugin, Image, UnidentifiedImageError

from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Sandbox
from support.rules import RULES

EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n"


def test_an_eps_file_named_png_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from agency.contracts.media import open_image

    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("an EPS image was loaded: Pillow would run Ghostscript")

    monkeypatch.setattr(EpsImagePlugin.EpsImageFile, "load", forbidden)
    monkeypatch.setattr(EpsImagePlugin, "Ghostscript", forbidden)
    with pytest.raises(UnidentifiedImageError):
        open_image(EPS)


def test_view_image_takes_the_media_type_from_the_content(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "JPEG")
    (tmp_path / "x.png").write_bytes(buffer.getvalue())
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        Ledger(tmp_path / "ledger.db"),
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    result = Toolbox(context).call("a", "view_image", {"path": "x.png"})
    assert not result.get("is_error")
    assert result["content"][0]["source"]["media_type"] == "image/jpeg"
