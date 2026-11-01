#!/usr/bin/env python3
"""Fogli di prova per loghi, renderizzati davvero alle dimensioni d'uso.

  logo_proof.py proof logo.svg --out proofs/          # dimensioni, mono, negativo, blur, sfondo
  logo_proof.py sheet a.svg b.svg c.svg --out sheet.png   # foglio di miniature per la selezione

Il rendering usa vectorcraft-cli (preferito), rsvg-convert o ImageMagick, nell'ordine.
Ogni dimensione è rasterizzata alla sua scala, non ridotta da un'immagine grande.
Richiede Pillow.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError:
    sys.exit("Pillow non disponibile: logo_proof.py richiede il modulo PIL")

SIZES = [16, 24, 32, 48, 64, 128, 512]
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def svg_size(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    head = text[: text.find(">", text.find("<svg")) + 1]
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', head)
    if vb:
        vals = [float(v) for v in re.findall(NUM, vb.group(1))]
        if len(vals) == 4:
            return vals[2], vals[3]
    w = re.search(rf'width\s*=\s*"({NUM})', head)
    h = re.search(rf'height\s*=\s*"({NUM})', head)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    sys.exit(f"{path}: impossibile ricavare le dimensioni (viewBox o width/height)")


def render(svg, longest_px, out_png):
    w, h = svg_size(svg)
    scale = longest_px / max(w, h)
    if shutil.which("vectorcraft-cli"):
        cmd = ["vectorcraft-cli", "convert", str(svg), str(out_png), "--scale", f"{scale:.6f}"]
    elif shutil.which("rsvg-convert"):
        cmd = ["rsvg-convert", "-z", f"{scale:.6f}", "-o", str(out_png), str(svg)]
    elif shutil.which("magick"):
        cmd = ["magick", "-background", "none", "-density", f"{72 * scale:.3f}", str(svg), str(out_png)]
    else:
        sys.exit("nessun renderer SVG disponibile (vectorcraft-cli, rsvg-convert, magick)")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not Path(out_png).exists():
        sys.exit(f"rendering fallito: {' '.join(cmd)}\n{res.stderr or res.stdout}")
    img = Image.open(out_png).convert("RGBA")
    img.load()
    return img


def silhouette(img, color):
    """Forma piena in un colore, dall'alpha del rendering."""
    alpha = img.getchannel("A")
    solid = Image.new("RGBA", img.size, color)
    solid.putalpha(alpha)
    return solid


def on(bg, img, pad=0):
    canvas = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), bg)
    canvas.alpha_composite(img, (pad, pad))
    return canvas


def label(img, text, fg, bg):
    band = 18
    out = Image.new("RGBA", (max(img.width, 7 * len(text) + 8), img.height + band), bg)
    out.alpha_composite(img, (0, 0))
    ImageDraw.Draw(out).text((4, img.height + 3), text, fill=fg)
    return out


def row(images, gap, bg):
    w = sum(i.width for i in images) + gap * (len(images) + 1)
    h = max(i.height for i in images) + 2 * gap
    out = Image.new("RGBA", (w, h), bg)
    x = gap
    for i in images:
        out.alpha_composite(i, (x, gap + (h - 2 * gap - i.height)))
        x += i.width + gap
    return out


def column(images, bg):
    w = max(i.width for i in images)
    out = Image.new("RGBA", (w, sum(i.height for i in images)), bg)
    y = 0
    for i in images:
        out.alpha_composite(i, (0, y))
        y += i.height
    return out


def register_render(source, proofs):
    """Registra il render in .agency/renders.jsonl (come render.py) per evidence.py."""
    import hashlib, json, os
    from datetime import datetime
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[4])
    def rel(p):
        p = Path(p).resolve()
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "source": rel(source),
             "source_sha": hashlib.sha256(Path(source).read_bytes()).hexdigest(), "proofs": [rel(x) for x in proofs]}
    manifest = root / ".agency/renders.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_proof(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    light, dark = (255, 255, 255, 255), (17, 17, 19, 255)
    ink = (17, 17, 19, 255)
    with tempfile.TemporaryDirectory() as tmp:
        renders = {s: render(args.svg, s, Path(tmp) / f"r{s}.png") for s in SIZES}
        big = render(args.svg, 1024, Path(tmp) / "r1024.png")

    small = [s for s in SIZES if s <= 128]  # il 512 compare nella riga dei test
    sizes_pos = row([label(on(light, renders[s]), f"{s}px", ink, light) for s in small], 16, light)
    sizes_mono = row([label(on(light, silhouette(renders[s], ink)), f"mono {s}", ink, light) for s in small], 16, light)
    sizes_neg = row([label(on(dark, silhouette(renders[s], (255, 255, 255, 255))), f"neg {s}", (230, 230, 230, 255), dark)
                     for s in small], 16, dark)
    mono512 = on(light, silhouette(renders[512], ink), 32)
    blur = mono512.filter(ImageFilter.GaussianBlur(radius=args.blur))
    tests = [label(on(light, renders[512], 32), "colore 512", ink, light),
             label(mono512, "mono 512", ink, light),
             label(blur, f"blur r={args.blur}", ink, light),
             label(on(dark, silhouette(renders[512], (255, 255, 255, 255)), 32), "negativo 512", (230, 230, 230, 255), dark)]
    if args.background:
        bg = Image.open(args.background).convert("RGBA")
        bg = ImageOps.fit(bg, (mono512.width, mono512.height))
        for colour, name in (((255, 255, 255, 255), "su immagine, bianco"), (ink, "su immagine, nero")):
            layer = bg.copy()
            layer.alpha_composite(silhouette(renders[512], colour), (32, 32))
            tests.append(label(layer, name, ink, light))

    sheet = column([sizes_pos, sizes_mono, sizes_neg, row(tests, 16, light)], light)
    stem = Path(args.svg).stem
    sheet.convert("RGB").save(out / f"{stem}_proof.png")
    big.save(out / f"{stem}_1024.png")
    for s in (16, 32):
        # Ingrandimento a pixel netti: mostra cosa resta davvero a quella dimensione.
        on(light, renders[s]).resize((s * 16, s * 16), Image.NEAREST).convert("RGB").save(out / f"{stem}_{s}px_x16.png")
    written = [out / f"{stem}_proof.png", out / f"{stem}_1024.png", out / f"{stem}_16px_x16.png", out / f"{stem}_32px_x16.png"]
    register_render(args.svg, written)
    print("scritti: " + ", ".join(str(w) for w in written))
    print("Ora apri il foglio di prova con Read e guardalo.")


def cmd_sheet(args):
    light, ink = (255, 255, 255, 255), (17, 17, 19, 255)
    cells = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, svg in enumerate(args.svgs):
            big = silhouette(render(svg, args.cell, Path(tmp) / f"a{n}.png"), ink) if args.mono else \
                render(svg, args.cell, Path(tmp) / f"a{n}.png")
            small = silhouette(render(svg, 24, Path(tmp) / f"b{n}.png"), ink)
            cell = Image.new("RGBA", (args.cell + 24 + 36, args.cell + 24), light)
            cell.alpha_composite(big, (12 + (args.cell - big.width) // 2, 12 + (args.cell - big.height) // 2))
            cell.alpha_composite(small, (args.cell + 24, 12))
            cells.append(label(cell, Path(svg).stem[:28], ink, light))
    cols = max(1, args.columns)
    rows_ = [row(cells[i:i + cols], 8, light) for i in range(0, len(cells), cols)]
    column(rows_, light).convert("RGB").save(args.out)
    print(f"scritto: {args.out} ({len(cells)} candidati)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("proof")
    s.add_argument("svg")
    s.add_argument("--out", required=True, help="cartella di output")
    s.add_argument("--blur", type=float, default=14, help="raggio del blur di silhouette sul 512")
    s.add_argument("--background", help="immagine/texture per la prova su fondo")
    s.set_defaults(fn=cmd_proof)
    s = sub.add_parser("sheet")
    s.add_argument("svgs", nargs="+")
    s.add_argument("--out", required=True, help="file PNG di output")
    s.add_argument("--cell", type=int, default=160)
    s.add_argument("--columns", type=int, default=6)
    s.add_argument("--mono", action="store_true", help="miniature in silhouette nera")
    s.set_defaults(fn=cmd_sheet)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
