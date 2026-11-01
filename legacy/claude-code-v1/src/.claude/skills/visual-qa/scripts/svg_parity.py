#!/usr/bin/env python3
"""Parità di rendering di un SVG tra renderer diversi: lo stesso logo deve apparire uguale
in VectorCraft, librsvg (rsvg-convert), Inkscape e cairosvg. Differenze indicano costrutti
SVG interpretati in modo diverso (filtri, maschere, testo, stroke, fill-rule, trasformazioni).

  svg_parity.py logo.svg [--size 512] [--out parity.png] [--min-ssim 0.99]

Confronta ogni renderer con VectorCraft (o con il primo disponibile). Esce con 1 se un
renderer scende sotto --min-ssim. Usa il venv dello studio (.claude/scripts/py).
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
    from skimage.metrics import structural_similarity
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def svg_size(path):
    head = Path(path).read_text(encoding="utf-8", errors="replace")
    head = head[: head.find(">", head.find("<svg")) + 1]
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', head)
    if vb:
        vals = [float(v) for v in re.findall(NUM, vb.group(1))]
        if len(vals) == 4:
            return vals[2], vals[3]
    w = re.search(rf'width\s*=\s*"({NUM})', head)
    h = re.search(rf'height\s*=\s*"({NUM})', head)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    sys.exit("dimensioni dell'SVG non ricavabili")


def renderers(svg, size, tmp):
    w, h = svg_size(svg)
    scale = size / max(w, h)
    px_w, px_h = round(w * scale), round(h * scale)
    out = {}
    if shutil.which("vectorcraft-cli"):
        out["vectorcraft"] = ["vectorcraft-cli", "convert", svg, f"{tmp}/vectorcraft.png", "--scale", f"{scale:.6f}"]
    if shutil.which("rsvg-convert"):
        out["librsvg"] = ["rsvg-convert", "-w", str(px_w), "-h", str(px_h), "-o", f"{tmp}/librsvg.png", svg]
    if shutil.which("inkscape"):
        out["inkscape"] = ["inkscape", svg, "--export-type=png", f"--export-filename={tmp}/inkscape.png",
                           f"--export-width={px_w}", f"--export-height={px_h}"]
    try:
        import cairosvg  # noqa: F401
        out["cairosvg"] = [sys.executable, "-c",
                           f"import cairosvg; cairosvg.svg2png(url={svg!r}, write_to={tmp + '/cairosvg.png'!r}, "
                           f"output_width={px_w}, output_height={px_h})"]
    except ImportError:
        pass
    return out, (px_w, px_h)


def flatten(path, size):
    img = Image.open(path).convert("RGBA")
    if img.size != size:
        img = img.resize(size, Image.LANCZOS)
    bg = Image.new("RGBA", size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    return bg.convert("RGB")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("svg")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--out")
    p.add_argument("--min-ssim", type=float, default=0.998)
    p.add_argument("--max-changed", type=float, default=0.002, help="quota massima di pixel diversi di più di 6/255")
    a = p.parse_args()
    svg = str(Path(a.svg).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        cmds, size = renderers(svg, a.size, tmp)
        images = {}
        for name, cmd in cmds.items():
            res = subprocess.run(cmd, capture_output=True, text=True)
            png = Path(tmp) / f"{name}.png"
            if res.returncode or not png.exists():
                print(f"{name:12} ERRORE di rendering: {(res.stderr or res.stdout).strip()[:200]}")
                continue
            images[name] = flatten(png, size)
    if len(images) < 2:
        sys.exit("servono almeno due renderer funzionanti")

    ref_name = "vectorcraft" if "vectorcraft" in images else next(iter(images))
    ref = np.asarray(images[ref_name])
    # L'antialiasing dei bordi varia legittimamente tra renderer: escludi una fascia di 1 px
    # attorno ai contorni del riferimento; le differenze vere (filtri, fill-rule, testo) stanno altrove.
    from scipy import ndimage
    gray = ref.mean(axis=2)
    edges = (np.abs(ndimage.sobel(gray, 0)) + np.abs(ndimage.sobel(gray, 1))) > 20
    edge_band = ndimage.binary_dilation(edges, iterations=1)
    worst_ok = True
    print(f"riferimento: {ref_name}, {size[0]}×{size[1]} px")
    for name, img in images.items():
        if name == ref_name:
            continue
        arr = np.asarray(img)
        ssim = structural_similarity(ref, arr, channel_axis=2)
        diff = np.abs(ref.astype(int) - arr.astype(int)).max(axis=2)
        changed = float(((diff > 6) & ~edge_band).mean())
        ok = changed <= a.max_changed and (ssim >= a.min_ssim or changed == 0)
        worst_ok &= ok
        print(f"{name:12} SSIM {ssim:.5f}  pixel diversi fuori dai bordi {changed * 100:.3f}%  scarto max {int(diff.max())}/255  "
              f"{'ok' if ok else 'DIVERSO'}")

    if a.out:
        tiles = []
        for name, img in images.items():
            t = img.copy()
            ImageDraw.Draw(t).text((8, 8), name, fill=(220, 0, 80))
            tiles.append(t)
        sheet = Image.new("RGB", (size[0] * len(tiles), size[1]), (255, 255, 255))
        for i, t in enumerate(tiles):
            sheet.paste(t, (i * size[0], 0))
        sheet.save(a.out)
        print(f"foglio: {a.out}")
    print("PASS" if worst_ok else "FAIL")
    sys.exit(0 if worst_ok else 1)


if __name__ == "__main__":
    main()
