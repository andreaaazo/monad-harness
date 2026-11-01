#!/usr/bin/env python3
"""Controllo tecnico di immagini di consegna: dimensioni, modalità, alpha, profilo ICC,
DPI dichiarati, peso; confronto con una specifica attesa.

  image_check.py file.png [altri…] [--expect 1080x1350] [--alpha required|forbidden]
                 [--print-mm 210x297 --min-ppi 300] [--max-kb 500] [--json]
"""
import argparse
import io
import json
import os
import sys

try:
    from PIL import Image, ImageCms
except ImportError:
    sys.exit("Pillow mancante: bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")


def check(path, a):
    img = Image.open(path)
    info = {"file": path, "format": img.format, "size": list(img.size), "mode": img.mode,
            "kb": round(os.path.getsize(path) / 1024, 1), "dpi": img.info.get("dpi"), "icc": None, "issues": []}
    icc = img.info.get("icc_profile")
    if icc:
        try:
            info["icc"] = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()
        except Exception:
            info["icc"] = "presente, non leggibile"
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if has_alpha:
        lo, _ = img.convert("RGBA").getchannel("A").getextrema()
        info["alpha"] = "usato" if lo < 255 else "canale presente ma opaco"
    else:
        info["alpha"] = "assente"
    if a.expect:
        w, h = (int(v) for v in a.expect.lower().split("x"))
        if tuple(img.size) != (w, h):
            info["issues"].append(f"dimensioni {img.size[0]}×{img.size[1]} ≠ attese {w}×{h}")
    if a.alpha == "required" and info["alpha"] != "usato":
        info["issues"].append("trasparenza richiesta ma assente")
    if a.alpha == "forbidden" and info["alpha"] == "usato":
        info["issues"].append("trasparenza presente dove non ammessa")
    if a.print_mm:
        wmm, hmm = (float(v) for v in a.print_mm.lower().split("x"))
        ppi = min(img.size[0] / (wmm / 25.4), img.size[1] / (hmm / 25.4))
        info["ppi_at_print_size"] = round(ppi)
        if ppi < a.min_ppi:
            info["issues"].append(f"{round(ppi)} ppi alla dimensione di stampa < {a.min_ppi}")
    if a.max_kb and info["kb"] > a.max_kb:
        info["issues"].append(f"peso {info['kb']} KB > {a.max_kb} KB")
    if img.mode in ("RGB", "RGBA") and not icc:
        info["warning"] = "nessun profilo ICC: interpretato come sRGB dalla maggior parte dei software"
    if img.mode == "CMYK" and not icc:
        info["issues"].append("CMYK senza profilo ICC: colore non definito")
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+")
    p.add_argument("--expect")
    p.add_argument("--alpha", choices=["required", "forbidden"])
    p.add_argument("--print-mm")
    p.add_argument("--min-ppi", type=float, default=300)
    p.add_argument("--max-kb", type=float)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    results = [check(f, a) for f in a.files]
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            status = "FAIL" if r["issues"] else "PASS"
            print(f"{status} {r['file']}: {r['format']} {r['size'][0]}×{r['size'][1]} {r['mode']}, alpha {r['alpha']}, "
                  f"ICC {r['icc'] or '-'}, {r['kb']} KB" + (f", {r['ppi_at_print_size']} ppi" if "ppi_at_print_size" in r else ""))
            for i in r["issues"]:
                print(f"  ERRORE {i}")
            if "warning" in r:
                print(f"  AVVISO {r['warning']}")
    sys.exit(1 if any(r["issues"] for r in results) else 0)


if __name__ == "__main__":
    main()
