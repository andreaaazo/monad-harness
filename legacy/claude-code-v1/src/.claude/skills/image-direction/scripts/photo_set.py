#!/usr/bin/env python3
"""Coerenza e trattamento di un set fotografico di marca.

  photo_set.py measure <cartella|file…>                          # firma di ogni foto e scarti dal set
  photo_set.py treat <cartella> --recipe ricetta.json --out <cartella>   # ricetta riproducibile
  photo_set.py match <cartella> --out <cartella> [--strength 0.8]        # avvicina ogni foto alla mediana del set
  photo_set.py sheet <cartella> --out foglio.png                          # foglio di contatto da guardare

Firma per foto (in OKLab): luminosità media, contrasto (dev. standard di L), croma media,
temperatura (asse b: giallo/blu), tinta (asse a: magenta/verde). Una foto fuori set ha uno
di questi valori lontano dalla mediana (oltre --tol volte la deviazione assoluta mediana, con
soglie minime). È una misura: la coerenza di luce, soggetto e punto di vista si guarda.

Ricetta (JSON): {"exposure": 0.1, "contrast": 1.1, "saturation": 0.85, "temperature": 0.05,
"tint": 0.0, "grain": 0.02, "vignette": 0.15, "crop": "4:5", "max_side": 2400}
Per fotoritocco (rimozioni, maschere, riempimenti) si usa PhotoCraft (MCP o photocraft-cli).
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def files(args):
    out = []
    for a in args:
        p = Path(a)
        out += sorted(x for x in p.iterdir() if x.suffix.lower() in EXT) if p.is_dir() else [p]
    return out


def to_oklab(rgb):
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(lin @ M1.T)
    return lms @ M2.T


def signature(path):
    im = Image.open(path).convert("RGB")
    im.thumbnail((512, 512))
    lab = to_oklab(np.asarray(im).astype(float) / 255).reshape(-1, 3)
    L, A, B = lab[:, 0], lab[:, 1], lab[:, 2]
    return {"L": float(L.mean()), "contrast": float(L.std()), "chroma": float(np.hypot(A, B).mean()),
            "temperature": float(B.mean()), "tint": float(A.mean())}


MIN_DEV = {"L": 0.04, "contrast": 0.03, "chroma": 0.015, "temperature": 0.012, "tint": 0.01}


def cmd_measure(a):
    fs = files(a.paths)
    sigs = {str(f): signature(f) for f in fs}
    keys = list(MIN_DEV)
    med = {k: float(np.median([s[k] for s in sigs.values()])) for k in keys}
    mad = {k: max(float(np.median([abs(s[k] - med[k]) for s in sigs.values()])) * a.tol, MIN_DEV[k]) for k in keys}
    out_count = 0
    print(f"{len(fs)} foto · mediana: " + ", ".join(f"{k} {med[k]:.3f}" for k in keys))
    for f, s in sigs.items():
        off = [f"{k} {s[k] - med[k]:+.3f}" for k in keys if abs(s[k] - med[k]) > mad[k]]
        out_count += bool(off)
        print(f"  {'FUORI SET' if off else 'ok       '} {Path(f).name:28} " + " ".join(f"{k}={s[k]:.3f}" for k in keys)
              + (f"   ← {', '.join(off)}" if off else ""))
    spread = {k: float(np.std([s[k] for s in sigs.values()])) for k in keys}
    print("dispersione del set: " + ", ".join(f"{k} {v:.3f}" for k, v in spread.items()))
    print("SET " + ("COERENTE (misura)" if not out_count else f"{out_count} foto fuori set: guardale e decidi"))
    if a.json:
        Path(a.json).write_text(json.dumps({"median": med, "spread": spread, "photos": sigs}, indent=2))
    sys.exit(1 if out_count else 0)


def apply_recipe(im, r):
    arr = np.asarray(im.convert("RGB")).astype(float) / 255
    if r.get("exposure"):
        arr = arr * (2 ** r["exposure"])
    if r.get("contrast", 1) != 1:
        arr = (arr - 0.5) * r["contrast"] + 0.5
    if r.get("temperature") or r.get("tint"):
        t, g = r.get("temperature", 0), r.get("tint", 0)
        arr = arr + np.array([t, -g, -t]) * 0.5
    if r.get("saturation", 1) != 1:
        gray = arr.mean(axis=2, keepdims=True)
        arr = gray + (arr - gray) * r["saturation"]
    arr = np.clip(arr, 0, 1)
    if r.get("vignette"):
        h, w = arr.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)
        arr = arr * (1 - r["vignette"] * d[..., None] ** 2)
    if r.get("grain"):
        rng = np.random.default_rng(7)
        arr = arr + rng.normal(0, r["grain"], arr.shape[:2])[..., None]
    out = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))
    if r.get("crop"):
        cw, ch = (float(v) for v in r["crop"].split(":"))
        w, h = out.size
        target = cw / ch
        if w / h > target:
            nw = int(h * target)
            out = out.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / target)
            out = out.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    if r.get("max_side"):
        out.thumbnail((r["max_side"], r["max_side"]), Image.LANCZOS)
    return out


def cmd_treat(a):
    r = json.loads(Path(a.recipe).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in files([a.src]):
        apply_recipe(Image.open(f), r).save(out / (f.stem + ".jpg"), quality=92)
        print(f"trattata: {out / (f.stem + '.jpg')}")
    (out / "recipe.json").write_text(json.dumps(r, indent=2))


def cmd_match(a):
    fs = files([a.src])
    sigs = {f: signature(f) for f in fs}
    med = {k: float(np.median([s[k] for s in sigs.values()])) for k in MIN_DEV}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f, s in sigs.items():
        k = a.strength
        r = {"exposure": float(np.log2(max(med["L"], 1e-3) / max(s["L"], 1e-3))) * 2.2 * k,
             "contrast": 1 + (med["contrast"] / max(s["contrast"], 1e-3) - 1) * k,
             "saturation": 1 + (med["chroma"] / max(s["chroma"], 1e-3) - 1) * k,
             "temperature": (med["temperature"] - s["temperature"]) * 4 * k,
             "tint": -(med["tint"] - s["tint"]) * 4 * k}
        apply_recipe(Image.open(f), r).save(out / (f.stem + ".jpg"), quality=92)
        print(f"allineata: {f.name}  " + ", ".join(f"{x} {v:+.3f}" for x, v in r.items()))


def cmd_sheet(a):
    fs = files([a.src])
    cell = 320
    cols = min(4, len(fs))
    rows = (len(fs) + cols - 1) // cols
    board = Image.new("RGB", (cols * cell, rows * (cell + 20)), (235, 235, 232))
    for i, f in enumerate(fs):
        im = Image.open(f).convert("RGB")
        im.thumbnail((cell - 8, cell - 8))
        x, y = (i % cols) * cell, (i // cols) * (cell + 20)
        board.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        ImageDraw.Draw(board).text((x + 6, y + cell + 3), f.name[:40], fill=(30, 30, 30))
    board.save(a.out)
    print(f"foglio: {a.out} (guardalo)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("measure")
    s.add_argument("paths", nargs="+")
    s.add_argument("--tol", type=float, default=2.5)
    s.add_argument("--json")
    s.set_defaults(fn=cmd_measure)
    s = sub.add_parser("treat")
    s.add_argument("src")
    s.add_argument("--recipe", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_treat)
    s = sub.add_parser("match")
    s.add_argument("src")
    s.add_argument("--out", required=True)
    s.add_argument("--strength", type=float, default=0.8)
    s.set_defaults(fn=cmd_match)
    s = sub.add_parser("sheet")
    s.add_argument("src")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_sheet)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
