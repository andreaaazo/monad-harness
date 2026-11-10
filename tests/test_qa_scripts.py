import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/agency/qa/scripts/svg_audit.py"

PATH = '<path id="p" d="M 10 10 L 50 10 L 50 40 L 10 40 Z"{attrs}/>'


def svg(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{body}</svg>'


def audit(tmp_path: Path, document: str) -> tuple[int, list[str]]:
    target = tmp_path / "logo.svg"
    target.write_text(document, encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(target), "--json"], capture_output=True, text=True, check=False
    )
    assert run.returncode in (0, 1), run.stderr
    return run.returncode, json.loads(run.stdout)["warnings"]


def test_svg_audit_flags_a_stroke_inherited_from_a_group(tmp_path: Path) -> None:
    group = f'<g stroke="#000" stroke-width="8" fill="none">{PATH.format(attrs="")}</g>'
    code, warnings = audit(tmp_path, svg(group))
    assert code == 1
    assert warnings == ["tratto non espanso su <path id=p> (stroke=#000)"]


def test_svg_audit_flags_a_style_element(tmp_path: Path) -> None:
    code, warnings = audit(tmp_path, svg("<style>.a{stroke:#000}</style>" + PATH.format(attrs="")))
    assert code == 1
    assert warnings == [
        "foglio di stile <style>: stili non verificabili, scriverli come attributi sugli elementi"
    ]


def test_svg_audit_lets_a_path_turn_off_an_inherited_stroke(tmp_path: Path) -> None:
    group = f'<g stroke="#000" stroke-width="8" fill="none">{PATH.format(attrs=' stroke="none"')}</g>'
    assert audit(tmp_path, svg(group)) == (0, [])


def test_svg_audit_ignores_an_inherited_stroke_on_non_graphics_elements(tmp_path: Path) -> None:
    group = f'<g stroke="#000"><title>logo</title>{PATH.format(attrs=' stroke="none"')}</g>'
    assert audit(tmp_path, svg(group)) == (0, [])


def test_svg_audit_follows_inherit_to_the_parent_stroke(tmp_path: Path) -> None:
    group = f'<g stroke="#000">{PATH.format(attrs=' stroke="inherit"')}</g>'
    code, warnings = audit(tmp_path, svg(group))
    assert (code, warnings) == (1, ["tratto non espanso su <path id=p> (stroke=#000)"])


def test_svg_audit_stops_an_inherited_stroke_at_a_nested_none(tmp_path: Path) -> None:
    group = f'<g stroke="#000"><g stroke="none">{PATH.format(attrs="")}</g></g>'
    assert audit(tmp_path, svg(group)) == (0, [])


def test_svg_audit_lets_the_inline_style_stroke_beat_the_attribute(tmp_path: Path) -> None:
    code, warnings = audit(tmp_path, svg(PATH.format(attrs=' stroke="none" style="stroke:#000"')))
    assert code == 1
    assert warnings == ["tratto non espanso su <path id=p> (stroke=#000)"]


def test_svg_audit_lets_an_inline_style_none_beat_the_stroke_attribute(tmp_path: Path) -> None:
    assert audit(tmp_path, svg(PATH.format(attrs=' stroke="#000" style="stroke:none"'))) == (0, [])


def test_svg_audit_takes_the_last_style_declaration_of_a_property(tmp_path: Path) -> None:
    assert audit(tmp_path, svg(PATH.format(attrs=' style="stroke:#000; stroke:none"'))) == (0, [])
    code, _ = audit(tmp_path, svg(PATH.format(attrs=' style="stroke:none; stroke : #000"')))
    assert code == 1


def test_svg_audit_flags_the_five_properties_written_in_the_inline_style(tmp_path: Path) -> None:
    cases = {
        "transform": ("transform:rotate(5)", "transform non applicato"),
        "opacity": ("opacity:.5", "opacità"),
        "mask": ("mask:url(#m)", "maschera"),
        "filter": ("filter:url(#f)", "filtro"),
        "clip-path": ("clip-path:url(#c)", "clip-path"),
    }
    for declaration, message in cases.values():
        code, warnings = audit(tmp_path, svg(PATH.format(attrs=f' style="fill:#000;{declaration}"')))
        assert code == 1, declaration
        assert warnings == [f"{message} su <path id=p>"], declaration


def test_svg_audit_does_not_confuse_similar_style_properties(tmp_path: Path) -> None:
    style = "fill-opacity:.5; stroke-width:4; stroke-opacity:1; -x-filter:1"
    assert audit(tmp_path, svg(PATH.format(attrs=f' style="{style}"'))) == (0, [])
