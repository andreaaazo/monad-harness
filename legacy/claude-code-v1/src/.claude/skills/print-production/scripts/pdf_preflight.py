#!/usr/bin/env python3
"""Preflight di un PDF: pagine e box, abbondanza, font incorporati, immagini (ppi effettivi
e spazio colore), output intent, copertura massima d'inchiostro (TAC) per pagina.

  pdf_preflight.py file.pdf [--print] [--bleed-mm 3] [--min-ppi 300] [--max-tac 300] [--json]

--print attiva i requisiti di stampa (abbondanza, CMYK, ppi, TAC). I limiti vanno presi
dalla specifica dello stampatore; i default sono valori d'uso comune, non universali.
Il TAC è misurato rasterizzando in CMYK con Ghostscript a 50 dpi (picchi più piccoli
di un pixel a quella risoluzione non vengono visti). Usa il venv (.claude/scripts/py).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf as fitz
    import numpy as np
    from PIL import Image
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

PT_MM = 25.4 / 72


def mm(v):
    return round(v * PT_MM, 2)


def fonts_report(path):
    if not shutil.which("pdffonts"):
        return None, ["pdffonts assente: font non verificati"]
    out = subprocess.run(["pdffonts", path], capture_output=True, text=True).stdout.splitlines()[2:]
    fonts, issues = [], []
    for line in out:
        parts = line.split()
        if len(parts) < 7:
            continue
        # Colonne finali: emb sub uni object ID — il nome può contenere spazi solo raramente.
        emb, sub = parts[-5], parts[-4]
        fonts.append({"name": parts[0], "embedded": emb == "yes", "subset": sub == "yes"})
        if emb != "yes":
            issues.append(f"font non incorporato: {parts[0]}")
    return fonts, issues


def tac(path, pages, dpi=50):
    if not shutil.which("gs"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=tiff32nc", f"-r{dpi}",
               f"-sOutputFile={tmp}/p%03d.tif", path]
        if subprocess.run(cmd, capture_output=True).returncode:
            return None
        res = []
        for i in range(pages):
            f = Path(tmp) / f"p{i + 1:03d}.tif"
            if not f.exists():
                res.append(None)
                continue
            arr = np.asarray(Image.open(f)).astype(np.uint16)
            total = arr.sum(axis=2) / 255 * 100
            res.append({"max": round(float(total.max()), 1), "p99": round(float(np.percentile(total, 99)), 1)})
        return res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pdf")
    p.add_argument("--print", dest="for_print", action="store_true")
    p.add_argument("--bleed-mm", type=float, default=3.0)
    p.add_argument("--min-ppi", type=float, default=300)
    p.add_argument("--max-tac", type=float, default=300)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    doc = fitz.open(a.pdf)
    report = {"file": a.pdf, "pages": doc.page_count, "pdf_version": doc.metadata.get("format"),
              "output_intent": None, "page_info": [], "issues": [], "warnings": []}
    try:
        from pypdf import PdfReader
        root = PdfReader(a.pdf).trailer["/Root"]
        if "/OutputIntents" in root:
            oi = root["/OutputIntents"][0].get_object()
            report["output_intent"] = str(oi.get("/OutputConditionIdentifier") or oi.get("/S"))
    except Exception as exc:  # pypdf non deve bloccare il preflight
        report["warnings"].append(f"output intent non letto: {exc}")

    fonts, font_issues = fonts_report(a.pdf)
    report["fonts"] = fonts
    report["issues"] += font_issues

    for i, page in enumerate(doc):
        media, trim, bleed = page.mediabox, page.trimbox, page.bleedbox
        info = {"page": i + 1, "media_mm": [mm(media.width), mm(media.height)],
                "trim_mm": [mm(trim.width), mm(trim.height)], "images": []}
        has_trim = trim != media
        bleed_mm = min(mm(trim.x0 - bleed.x0), mm(bleed.x1 - trim.x1), mm(trim.y0 - bleed.y0), mm(bleed.y1 - trim.y1)) \
            if has_trim else 0.0
        info["bleed_mm"] = round(bleed_mm, 2)
        if a.for_print and not has_trim:
            report["issues"].append(f"p{i + 1}: TrimBox assente (o uguale al MediaBox): nessuna abbondanza definita")
        elif a.for_print and bleed_mm + 0.01 < a.bleed_mm:
            report["issues"].append(f"p{i + 1}: abbondanza {bleed_mm} mm < {a.bleed_mm} mm")
        for img in page.get_image_info(xrefs=True):
            w_in = (img["bbox"][2] - img["bbox"][0]) / 72
            h_in = (img["bbox"][3] - img["bbox"][1]) / 72
            if w_in <= 0 or h_in <= 0:
                continue
            ppi = min(img["width"] / w_in, img["height"] / h_in)
            cs = img.get("cs-name") or str(img.get("colorspace"))
            info["images"].append({"xref": img.get("xref"), "px": [img["width"], img["height"]],
                                   "ppi": round(ppi), "colorspace": cs})
            if a.for_print and ppi < a.min_ppi:
                report["issues"].append(f"p{i + 1}: immagine xref {img.get('xref')} a {round(ppi)} ppi < {a.min_ppi}")
            if a.for_print and "RGB" in str(cs).upper():
                report["warnings"].append(f"p{i + 1}: immagine RGB (xref {img.get('xref')}): conversione a cura del RIP")
        report["page_info"].append(info)

    if a.for_print:
        coverage = tac(a.pdf, doc.page_count)
        if coverage is None:
            report["warnings"].append("TAC non misurato (Ghostscript assente o errore)")
        else:
            for i, c in enumerate(coverage):
                if c is None:
                    continue
                report["page_info"][i]["tac"] = c
                if c["max"] > a.max_tac:
                    report["issues"].append(f"p{i + 1}: TAC massimo {c['max']}% > {a.max_tac}%")
        if not report["output_intent"]:
            report["warnings"].append("nessun output intent (PDF/X): condizione di stampa non dichiarata")

    report["result"] = "FAIL" if report["issues"] else "PASS"
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{a.pdf}: {report['pages']} pagine, {report['pdf_version']}, output intent: {report['output_intent']}")
        for pi in report["page_info"]:
            print(f"  p{pi['page']}: media {pi['media_mm']} mm, trim {pi['trim_mm']} mm, abbondanza {pi['bleed_mm']} mm"
                  + (f", TAC max {pi['tac']['max']}%" if 'tac' in pi else "") + f", immagini {len(pi['images'])}")
        if fonts is not None:
            print(f"  font: {len(fonts)} ({sum(f['embedded'] for f in fonts)} incorporati)")
        for w in report["warnings"]:
            print(f"  AVVISO {w}")
        for e in report["issues"]:
            print(f"  ERRORE {e}")
        print(report["result"])
    sys.exit(1 if report["issues"] else 0)


if __name__ == "__main__":
    main()
