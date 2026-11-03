"""La tavola del giudizio alla cieca: ogni disegno alla stessa misura, grande e alle misure d'uso (ADR-0041).

Le tele sono quelle dei due `segno.svg` reali: 98 × 118,5 px con il disegno al 91%, 800 × 600 px con
il disegno al 76%. Messi nello stesso riquadro per la loro tela, il primo sembrerebbe più grande di un
quinto.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from agency.evaluation import board
from agency.evaluation.blind import CannotCompare
from drawings import INK, FakeVectorcraft, svg

TIGHT = svg((98, 118.5), (6, 6, 86, 108))
LOOSE = svg((800, 600), (99, 115, 609, 355))
SIZES = (board.LARGE, *board.SMALL)


def write(path: Path, body: str | Image.Image) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, Image.Image):
        body.save(path)
    else:
        path.write_text(body, encoding="utf-8")
    return path


def longest(image: Image.Image) -> int:
    return max(image.size)


def ink_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Dove c'è inchiostro su una tavola bianca."""
    return Image.eval(image.convert("L"), lambda value: 255 if value < 128 else 0).getbbox()


def test_every_drawing_has_the_same_size_whatever_its_canvas(tmp_path: Path) -> None:
    render = FakeVectorcraft()
    for name, body in (("A.svg", TIGHT), ("B.svg", LOOSE)):
        drawn = board.drawn(write(tmp_path / name, body), render, tmp_path)
        assert set(drawn) == set(SIZES)
        for size, image in drawn.items():
            assert abs(longest(image) - size) <= 1, (name, size, image.size)


def test_small_sizes_are_rendered_at_their_own_scale_not_reduced_from_the_large_one(tmp_path: Path) -> None:
    """Come in logo_proof: a 16 px conta cosa resta di un disegno reso a 16 px."""
    render = FakeVectorcraft()
    board.drawn(write(tmp_path / "A.svg", TIGHT), render, tmp_path)
    for size in SIZES:  # il lato più lungo del disegno è 108 px della tela
        assert any(abs(scale - size / 108) <= size / 108 / 100 for scale in render.scales), size


def test_a_raster_is_measured_on_what_is_drawn_not_on_its_transparent_canvas(tmp_path: Path) -> None:
    padded = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    padded.paste(INK, (100, 30, 150, 70))
    drawn = board.drawn(write(tmp_path / "A.png", padded), None, tmp_path)
    for size, image in drawn.items():
        assert image.size == (size, round(size * 40 / 50)), size


def test_the_board_puts_every_letter_in_the_same_square_on_white(tmp_path: Path) -> None:
    folder = tmp_path / "blind"
    copies = {"A": write(folder / "A.svg", TIGHT), "B": write(folder / "B.svg", LOOSE)}

    sheet = board.lay_board(copies, folder, FakeVectorcraft())

    assert sheet is not None and sheet == folder / "tavola.png"
    assert sorted(path.name for path in folder.iterdir()) == ["A.svg", "B.svg", "tavola.png"]
    with Image.open(sheet) as opened:
        assert (opened.format, opened.mode, opened.size) == ("PNG", "RGB", (2 * board.CELL, board.ROW))
        assert not opened.info.keys() - {"dpi"}, opened.info  # nessun testo: né titoli né percorsi
        image = opened.copy()
    assert image.getpixel((0, 0)) == (255, 255, 255)
    for column in range(2):
        square = image.crop((column * board.CELL, 0, (column + 1) * board.CELL, board.CELL))
        box = ink_box(square)
        assert box is not None
        assert abs(max(box[2] - box[0], box[3] - box[1]) - board.LARGE) <= 1, column
        middle = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        assert all(abs(axis - board.CELL / 2) <= 1 for axis in middle), (column, middle)


def test_many_files_wrap_after_three_columns(tmp_path: Path) -> None:
    folder = tmp_path / "blind"
    copies = {
        letter: write(folder / f"{letter}.svg", svg((100, 100), (10, 10, 20 + index, 30)))
        for index, letter in enumerate("ABCD")
    }
    sheet = board.lay_board(copies, folder, FakeVectorcraft())
    assert sheet is not None
    with Image.open(sheet) as opened:
        assert opened.size == (3 * board.CELL, 2 * board.ROW)


def test_a_type_without_a_board_gets_none_and_writes_nothing(tmp_path: Path) -> None:
    folder = tmp_path / "blind"
    copies = {"A": write(folder / "A.pdf", "%PDF-1.7 a"), "B": write(folder / "B.pdf", "%PDF-1.7 b")}
    assert board.lay_board(copies, folder, FakeVectorcraft()) is None
    assert sorted(path.name for path in folder.iterdir()) == ["A.pdf", "B.pdf"]


def test_without_the_renderer_svgs_are_refused_not_shown_unequal(tmp_path: Path) -> None:
    folder = tmp_path / "blind"
    copies = {"A": write(folder / "A.svg", TIGHT), "B": write(folder / "B.svg", LOOSE)}
    with pytest.raises(CannotCompare, match="vectorcraft-cli manca"):
        board.lay_board(copies, folder, None)


def test_an_empty_drawing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CannotCompare, match=r"A\.svg non ha niente di disegnato"):
        board.drawn(write(tmp_path / "A.svg", svg((100, 100), (10, 10, 0, 0))), FakeVectorcraft(), tmp_path)


def test_a_speck_on_a_huge_canvas_is_refused_before_an_enormous_render(tmp_path: Path) -> None:
    render = FakeVectorcraft()
    with pytest.raises(CannotCompare, match="parte troppo piccola"):
        board.drawn(write(tmp_path / "A.svg", svg((2000, 2000), (0, 0, 1, 1))), render, tmp_path)
    assert max(render.scales) <= 1  # la tela misurata, non quella enorme


# Il renderer vero


@pytest.fixture
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un vectorcraft-cli finto che annota il suo ambiente e fallisce come fallirebbe su un file rotto.

    Prima di fallire lascia un'uscita a metà: conta il codice d'uscita, non l'esistenza del file.
    """
    folder = tmp_path / "bin"
    folder.mkdir()
    binary = folder / "vectorcraft-cli"
    binary.write_text(
        '#!/bin/sh\nenv > "$(dirname "$0")/environment"\necho partial > "$3"\n'
        'echo "parse error at line 1" >&2\nexit 3\n',
        encoding="utf-8",
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}:/usr/bin:/bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "board-canary-not-a-key")
    monkeypatch.setenv("AGENCY_ANTHROPIC_API_KEY", "board-canary-not-a-key")
    return binary


def test_the_renderer_gets_only_path_and_home_never_the_key(fake_binary: Path, tmp_path: Path) -> None:
    render = board.vectorcraft()
    assert render is not None
    failure = r"A\.svg non si rende con vectorcraft-cli: parse error at line 1"
    with pytest.raises(CannotCompare, match=failure):
        render(write(tmp_path / "A.svg", TIGHT), 1.0, tmp_path / "out.png")
    seen = (fake_binary.parent / "environment").read_text(encoding="utf-8")
    assert "board-canary-not-a-key" not in seen
    names = {line.split("=", 1)[0] for line in seen.splitlines()}
    assert {"PATH", "HOME"} >= names - {"PWD", "SHLVL", "_", "OLDPWD"}, names


def test_without_vectorcraft_on_the_path_there_is_no_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    assert board.vectorcraft() is None


@pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="manca vectorcraft-cli")
def test_with_the_real_renderer_both_canvases_give_the_same_drawing(tmp_path: Path) -> None:
    render = board.vectorcraft()
    assert render is not None
    for name, body in (("A.svg", TIGHT), ("B.svg", LOOSE)):
        drawn = board.drawn(write(tmp_path / name, body), render, tmp_path)
        for size, image in drawn.items():
            assert abs(longest(image) - size) <= 1, (name, size, image.size)
