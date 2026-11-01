#!/usr/bin/env python3
"""Immersione nel mondo del cliente: inventario osservabile dei materiali forniti.

  .claude/scripts/py .claude/skills/client-world/scripts/world_ingest.py [work/client] [--out work/context/world]

Per ogni file in work/client/ (cartelle comprese):
  immagini   → dimensioni, palette dominante misurata (OKLCH + HEX), foglio di contatto
  PDF        → pagine, testo estratto, font usati, foglio delle pagine
  Office     → convertiti in PDF (LibreOffice) e trattati come PDF
  SVG/AI/EPS → render con VectorCraft
  video      → durata e foglio di frame
  testo/md   → testo
Poi: lessico del cliente (parole e bigrammi più frequenti, lunghezza media delle frasi).

Scrive inventory.md, palette.json, lexicon.json, i testi estratti e i fogli di contatto.
I risultati sono FONTI (documenti del cliente): registrali come fatti con
`facts.py add --kind source --ref work/client/<file>`. Guarda i fogli con Read.
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[4])
IMG = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".heic"}
OFFICE = {".docx", ".doc", ".pptx", ".ppt", ".odt", ".odp", ".xlsx", ".ods", ".rtf"}
VECTOR = {".svg", ".ai", ".eps", ".pdf_vector"}
VIDEO = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
TEXT = {".txt", ".md", ".csv", ".html", ".htm"}
STOP = set("""a ad al alla alle allo agli ai anche che chi ci con da dal dalla dei del della delle dello degli di
e ed è era gli ha hanno i il in la le lo l loro ma mi ne nel nella nelle non o per più però po qui se si sia
sono su sua sue suo suoi tra un una uno vi voi noi questo questa questi queste come dove quando cosa
the and of to in is for on with as at by an be this that it are or from your our we you
der die das und ist zu den mit von im für ein eine auf nicht sich des dem als auch es an""".split())


def oklch(rgb):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    import math
    return round(L, 3), round(math.hypot(A, B), 3), round(math.degrees(math.atan2(B, A)) % 360, 1)


def palette(img, k=6):
    """Colori dominanti per k-means su pixel campionati; quota di superficie per colore."""
    small = img.convert("RGB")
    small.thumbnail((160, 160))
    px = np.asarray(small).reshape(-1, 3).astype(float)
    rng = np.random.default_rng(0)
    centers = px[rng.choice(len(px), size=min(k, len(px)), replace=False)]
    for _ in range(15):
        d = ((px[:, None, :] - centers[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        centers = np.array([px[lab == i].mean(0) if (lab == i).any() else centers[i] for i in range(len(centers))])
    share = np.bincount(lab, minlength=len(centers)) / len(px)
    out = []
    for c, sh in sorted(zip(centers, share), key=lambda x: -x[1]):
        if sh < 0.005:
            continue  # cluster vuoti o trascurabili
        rgb = tuple(int(round(v)) for v in c)
        if any(sum((x - y) ** 2 for x, y in zip(rgb, o["rgb"])) < 36 for o in out):
            continue  # quasi identico a un colore già trovato
        out.append({"hex": "#%02X%02X%02X" % rgb, "rgb": rgb, "oklch": oklch(rgb), "share": round(float(sh), 3)})
    return [{k: v for k, v in o.items() if k != "rgb"} for o in out]


def contact(paths, out, cell=300, cols=5):
    if not paths:
        return None
    tiles = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        im.thumbnail((cell, cell))
        t = Image.new("RGB", (cell, cell + 20), (250, 250, 250))
        t.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2))
        ImageDraw.Draw(t).text((4, cell + 4), Path(p).name[-48:], fill=(30, 30, 30))
        tiles.append(t)
    rows = (len(tiles) + cols - 1) // cols
    board = Image.new("RGB", (cols * cell, rows * (cell + 20)), (220, 220, 220))
    for i, t in enumerate(tiles):
        board.paste(t, ((i % cols) * cell, (i // cols) * (cell + 20)))
    board.save(out)
    return out


def pdf_info(path, out_dir):
    import pymupdf
    doc = pymupdf.open(path)
    text = "\n".join(p.get_text() for p in doc)
    thumbs = []
    for i, page in enumerate(doc):
        if i >= 24:
            break
        zoom = 500 / max(page.rect.width, page.rect.height)
        t = out_dir / f"{path.stem}_p{i + 1:02d}.png"
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(t)
        thumbs.append(t)
    fonts = []
    if shutil.which("pdffonts"):
        lines = subprocess.run(["pdffonts", str(path)], capture_output=True, text=True).stdout.splitlines()[2:]
        fonts = sorted({l.split()[0].split("+")[-1] for l in lines if l.strip()})
    return {"pages": doc.page_count, "fonts": fonts, "chars": len(text)}, text, thumbs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", default="work/client")
    p.add_argument("--out", default="work/context/world")
    a = p.parse_args()
    src = (ROOT / a.source) if not Path(a.source).is_absolute() else Path(a.source)
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    if not src.exists():
        sys.exit(f"{src} non esiste: metti lì i materiali del cliente (documenti, foto, logo, campioni)")
    (out / "text").mkdir(parents=True, exist_ok=True)
    (out / "previews").mkdir(parents=True, exist_ok=True)

    items, images, page_thumbs, texts, palettes = [], [], [], {}, {}
    for f in sorted(x for x in src.rglob("*") if x.is_file()):
        ext = f.suffix.lower()
        relp = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)
        item = {"file": relp, "kind": "altro", "kb": round(f.stat().st_size / 1024, 1)}
        try:
            if ext in IMG:
                im = Image.open(f)
                item.update(kind="immagine", size=list(im.size), mode=im.mode)
                palettes[relp] = palette(im)
                item["palette"] = [c["hex"] for c in palettes[relp][:4]]
                images.append(f)
            elif ext == ".pdf":
                info, text, thumbs = pdf_info(f, out / "previews")
                item.update(kind="pdf", **info)
                texts[relp] = text
                page_thumbs += thumbs
            elif ext in OFFICE:
                with tempfile.TemporaryDirectory() as tmp:
                    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, str(f)],
                                   capture_output=True, timeout=600)
                    pdf = Path(tmp) / f"{f.stem}.pdf"
                    if pdf.exists():
                        info, text, thumbs = pdf_info(pdf, out / "previews")
                        item.update(kind="documento", **info)
                        texts[relp] = text
                        page_thumbs += thumbs
            elif ext in VECTOR:
                dst = out / "previews" / f"{f.stem}_vector.png"
                subprocess.run(["vectorcraft-cli", "convert", str(f), str(dst), "--scale", "2"], capture_output=True, timeout=300)
                if dst.exists():
                    item.update(kind="vettoriale")
                    images.append(dst)
                    palettes[relp] = palette(Image.open(dst))
            elif ext in VIDEO:
                dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                     capture_output=True, text=True).stdout.strip()
                item.update(kind="video", duration_s=round(float(dur or 0), 2))
                for i in range(4):
                    t = float(dur or 0) * i / 4
                    dst = out / "previews" / f"{f.stem}_t{i}.png"
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(f), "-frames:v", "1", str(dst)])
                    if dst.exists():
                        images.append(dst)
            elif ext in TEXT:
                text = f.read_text(encoding="utf-8", errors="replace")
                if ext in (".html", ".htm"):
                    text = re.sub(r"<[^>]+>", " ", text)
                item.update(kind="testo", chars=len(text))
                texts[relp] = text
        except Exception as exc:  # un file illeggibile non deve fermare l'inventario
            item["error"] = str(exc)[:200]
        items.append(item)

    for relp, text in texts.items():
        (out / "text" / (Path(relp).name + ".txt")).write_text(text, encoding="utf-8")
    words = [w for t in texts.values() for w in re.findall(r"[a-zàèéìòóùäöüß']{3,}", t.lower()) if w not in STOP]
    bigrams = collections.Counter(zip(words, words[1:]))
    sentences = [s for t in texts.values() for s in re.split(r"[.!?]+", t) if len(s.split()) >= 3]
    lexicon = {"words": collections.Counter(words).most_common(40),
               "bigrams": [(" ".join(b), n) for b, n in bigrams.most_common(20)],
               "avg_sentence_words": round(sum(len(s.split()) for s in sentences) / len(sentences), 1) if sentences else None}
    (out / "palette.json").write_text(json.dumps(palettes, indent=2, ensure_ascii=False))
    (out / "lexicon.json").write_text(json.dumps(lexicon, indent=2, ensure_ascii=False))
    sheet_img = contact(images, out / "contact_images.png")
    sheet_pages = contact(page_thumbs, out / "contact_pages.png", cell=260, cols=6)

    md = ["# Mondo del cliente — inventario", "", f"Sorgente: `{a.source}` · {len(items)} file.",
          "Tutto ciò che segue è **FONTE** (documenti del cliente), non conferma del cliente.", "",
          "| File | Tipo | Dettagli |", "|---|---|---|"]
    for it in items:
        det = ", ".join(f"{k}: {v}" for k, v in it.items() if k not in ("file", "kind"))
        md.append(f"| `{it['file']}` | {it['kind']} | {det} |")
    md += ["", "## Lessico del cliente", "",
           "Parole frequenti: " + ", ".join(f"{w} ({n})" for w, n in lexicon["words"][:25]),
           "", "Bigrammi: " + ", ".join(f"{b} ({n})" for b, n in lexicon["bigrams"][:12]),
           "", f"Lunghezza media delle frasi: {lexicon['avg_sentence_words']} parole", "",
           "## Fogli da guardare", ""]
    for s in (sheet_img, sheet_pages):
        if s:
            md.append(f"- `{Path(s).relative_to(ROOT) if Path(s).is_relative_to(ROOT) else s}`")
    (out / "inventory.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"inventario: {out / 'inventory.md'}  ({len(items)} file, {len(texts)} testi, {len(images)} immagini)")
    for s in (sheet_img, sheet_pages):
        if s:
            print(f"guarda: {s}")


if __name__ == "__main__":
    main()
