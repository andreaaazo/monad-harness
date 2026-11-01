#!/usr/bin/env python3
"""Rende qualsiasi output dello studio in PNG da guardare, e registra quale versione è stata resa.

  .claude/scripts/py .claude/scripts/render.py <file…> [--out work/proofs/render] [--size 1200] [--frames 6] [--sheet]

Tipi: .figcraft/.fig/.sketch (FigCraft, un PNG per frame) · .pcraft/.psd (PhotoCraft) ·
.svg/.svgz · .vectorcraft/.ai/.eps (VectorCraft) · .pdf (pagine) · .html/.htm o URL
(Playwright, 1440 e 390 px) · .mp4/.mov/.webm/.gif (frame distribuiti + foglio) · .json Lottie
(lottie-web) · .ecproj (EffectCraft, frame distribuiti) · .docx/.pptx/.odt/.odp (LibreOffice → PDF)
· .png/.jpg/.webp/.tif (anteprima).

Ogni esecuzione aggiunge a .agency/renders.jsonl: sorgente, hash della sorgente, immagini prodotte.
evidence.py accetta una revisione visiva solo con una prova presente qui per la versione attuale.
Dopo il render, **apri le immagini con Read e guardale**: il render non è la revisione.
Ogni immagine letta costa contesto: 1200 px bastano per giudicare l'insieme, i dettagli si guardano
con --zoom, molti file si guardano con --sheet in un solo foglio.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow mancante: bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
MANIFEST = ROOT / ".agency/renders.jsonl"
SCRIPTS = Path(__file__).resolve().parent


def rel(p):
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, timeout=300):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]}: {(r.stderr or r.stdout).strip()[:400]}")
    return r.stdout


def sheet(images, out, cols=3, cell=520):
    tiles = []
    for p in images:
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell, cell))
        tile = Image.new("RGB", (cell, cell + 22), (255, 255, 255))
        tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2))
        ImageDraw.Draw(tile).text((6, cell + 5), Path(p).stem[-60:], fill=(40, 40, 40))
        tiles.append(tile)
    rows = (len(tiles) + cols - 1) // cols
    board = Image.new("RGB", (cols * cell, rows * (cell + 22)), (240, 240, 240))
    for i, t in enumerate(tiles):
        board.paste(t, ((i % cols) * cell, (i // cols) * (cell + 22)))
    board.save(out)
    return out


def r_svg(src, out, a):
    w = h = None
    import re
    head = src.read_text(encoding="utf-8", errors="replace")[:4000]
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', head)
    if vb:
        vals = [float(v) for v in re.split(r"[\s,]+", vb.group(1).strip())]
        w, h = vals[2], vals[3]
    scale = a.size / max(w or a.size, h or a.size)
    dst = out / f"{src.stem}.png"
    run(["vectorcraft-cli", "convert", src, dst, "--scale", f"{scale:.6f}"])
    return [dst]


def r_vector_doc(src, out, a):
    dst = out / f"{src.stem}.png"
    run(["vectorcraft-cli", "convert", src, dst, "--scale", str(a.scale)])
    return [dst]


def r_pdf(src, out, a):
    import pymupdf
    doc = pymupdf.open(src)
    pages = []
    for i, page in enumerate(doc):
        if i >= a.max_pages:
            break
        zoom = a.size / max(page.rect.width, page.rect.height)
        dst = out / f"{src.stem}_p{i + 1:03d}.png"
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(dst)
        pages.append(dst)
    if len(pages) > 1:
        pages.append(sheet(pages, out / f"{src.stem}_sheet.png", cols=4, cell=360))
    return pages


def r_office(src, out, a):
    with tempfile.TemporaryDirectory() as tmp:
        run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, src], timeout=600)
        pdf = Path(tmp) / f"{src.stem}.pdf"
        kept = out / pdf.name
        shutil.copy(pdf, kept)
    return r_pdf(kept, out, a)


def r_web(src, out, a):
    target = src if isinstance(src, str) else src.resolve().as_uri()
    stem = Path(src).stem if not isinstance(src, str) else "web"
    script = SCRIPTS / "render_web.mjs"
    run([SCRIPTS / "node", script, target, out, stem], timeout=300)
    return sorted(out.glob(f"{stem}_w*.png"))


def r_video(src, out, a):
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).strip() or 0)
    frames = []
    for i in range(a.frames):
        t = dur * (i / max(1, a.frames - 1)) if a.frames > 1 else 0
        t = min(t, max(0, dur - 0.05))
        dst = out / f"{src.stem}_t{t:07.3f}.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", dst])
        frames.append(dst)
    frames.append(sheet(frames, out / f"{src.stem}_sheet.png"))
    return frames


def r_lottie(src, out, a):
    positions = ",".join(f"{i / max(1, a.frames - 1):.3f}" for i in range(a.frames))
    lot = out / f"{src.stem}_lottie"
    subprocess.run([str(SCRIPTS / "node"), str(SCRIPTS.parent / "skills/motion-identity/scripts/lottie_check.mjs"),
                    str(src), "--out", str(lot), "--frames", positions], capture_output=True, text=True, timeout=300)
    frames = sorted(lot.glob("frame_*.png"))
    if not frames:
        raise RuntimeError("lottie-web non ha prodotto frame (vedi lottie_check.mjs)")
    frames.append(sheet(frames, out / f"{src.stem}_sheet.png"))
    return frames


def r_ecproj(src, out, a):
    info = json.loads(run(["effectcraft-cli", "info", "--project", src, "--json"]) or "{}")
    dur = float((info.get("activeComp") or {}).get("duration") or 0)
    frames = []
    for i in range(a.frames):
        t = dur * i / max(1, a.frames - 1) if dur else 0
        dst = out / f"{src.stem}_t{t:07.3f}.png"
        run(["effectcraft-cli", "render-frame", "--project", src, "--time", f"{t:.3f}", "--max-side", str(a.size), "--out", dst])
        frames.append(dst)
    if len(frames) > 1:
        frames.append(sheet(frames, out / f"{src.stem}_sheet.png"))
    return frames


def r_figcraft(src, out, a):
    """Un PNG per ogni frame di primo livello (tutte le pagine), poi un foglio d'insieme."""
    dest = out / f"{src.stem}_frames"
    dest.mkdir(parents=True, exist_ok=True)
    run(["figcraft-cli", "export", src, "-o", dest, "--format", "png", "--scale", str(a.figscale)], timeout=600)
    frames = sorted(dest.rglob("*.png"))
    info = subprocess.run(["figcraft-cli", "info", str(src), "--json"], capture_output=True, text=True)
    try:
        missing = json.loads(info.stdout).get("missingFonts") or []
    except json.JSONDecodeError:
        missing = []
    if missing:
        print(f"ATTENZIONE {src.name}: font mancanti {missing} — il render usa caratteri di ripiego")
    if len(frames) > 1:
        frames.append(sheet(frames, out / f"{src.stem}_sheet.png", cols=4, cell=420))
    return frames


def r_photocraft(src, out, a):
    dst = out / f"{src.stem}.png"
    run(["photocraft-cli", "convert", src, dst], timeout=600)
    return [dst]


def r_image(src, out, a):
    im = Image.open(src)
    im.thumbnail((a.size, a.size))
    dst = out / f"{src.stem}_preview.png"
    im.save(dst)
    return [dst]


HANDLERS = {
    (".svg", ".svgz"): r_svg, (".vectorcraft", ".ai", ".eps", ".afdesign"): r_vector_doc, (".pdf",): r_pdf,
    (".html", ".htm"): r_web, (".mp4", ".mov", ".webm", ".gif", ".mkv"): r_video, (".json", ".lottie"): r_lottie,
    (".ecproj",): r_ecproj, (".figcraft", ".fig", ".sketch"): r_figcraft, (".pcraft", ".psd", ".psb"): r_photocraft, (".docx", ".pptx", ".odt", ".odp", ".doc", ".ppt"): r_office,
    (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"): r_image,
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+")
    p.add_argument("--out", default="work/proofs/render")
    p.add_argument("--size", type=int, default=1200, help="lato lungo in px")
    p.add_argument("--scale", type=float, default=2.0, help="px per punto per i documenti vettoriali")
    p.add_argument("--frames", type=int, default=6)
    p.add_argument("--max-pages", type=int, default=60)
    p.add_argument("--figscale", type=float, default=1.0, help="scala dell'export dei frame FigCraft")
    p.add_argument("--zoom", action="append", default=[],
                   help="ingrandimento di un dettaglio: 'x,y,w,h' in frazioni 0–1 del render (ripetibile)")
    p.add_argument("--zoom-factor", type=float, default=2.0)
    p.add_argument("--sheet", action="store_true", help="un foglio di contatto con tutti i file resi: un'immagine sola da guardare")
    a = p.parse_args()
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    made = []
    for f in a.files:
        is_url = f.startswith(("http://", "https://"))
        src = f if is_url else Path(f).resolve()
        ext = "" if is_url else src.suffix.lower()
        handler = r_web if is_url else next((h for exts, h in HANDLERS.items() if ext in exts), None)
        if handler is None:
            print(f"NON SUPPORTATO {f}")
            failures += 1
            continue
        if not is_url and not src.exists():
            print(f"INESISTENTE {f}")
            failures += 1
            continue
        try:
            proofs = handler(src, out, a)
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            print(f"ERRORE {f}: {exc}")
            failures += 1
            continue
        # Le immagini grandi vengono ridotte quando si guardano: gli ingrandimenti mostrano i
        # dettagli (kerning, giunzioni, bordi) alla scala reale o oltre.
        for z in a.zoom:
            fx, fy, fw, fh = (float(v) for v in z.split(","))
            for base in [x for x in proofs if "_sheet" not in Path(x).name][:4]:
                im = Image.open(base)
                W, H = im.size
                box = (int(fx * W), int(fy * H), int((fx + fw) * W), int((fy + fh) * H))
                crop = im.crop(box)
                crop = crop.resize((int(crop.width * a.zoom_factor), int(crop.height * a.zoom_factor)), Image.LANCZOS)
                zp = Path(base).with_name(f"{Path(base).stem}_zoom_{fx:.2f}_{fy:.2f}.png")
                crop.save(zp)
                proofs.append(zp)
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "source": f if is_url else rel(src),
                 "source_sha": None if is_url else sha(src), "proofs": [rel(x) for x in proofs]}
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        made += [x for x in proofs if "_zoom_" not in Path(x).name and "_sheet" not in Path(x).name]
        print(f"RESO {entry['source']} →")
        for x in entry["proofs"]:
            print(f"  {x}")
    if a.sheet and len(made) > 1:
        print(f"FOGLIO {rel(sheet(made[:24], out / 'contact_sheet.png', cols=4, cell=300))}")
    if not failures:
        print("Ora apri le immagini con Read e guardale alla dimensione d'uso.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
