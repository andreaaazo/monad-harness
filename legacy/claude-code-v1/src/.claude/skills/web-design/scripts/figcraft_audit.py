#!/usr/bin/env python3
"""Audit di un file di design FigCraft (siti, app, interfacce) senza scrivere codice.

  figcraft_audit.py design.figcraft [--mobile-max 480] [--record-by ui-designer] [--json]

Legge l'albero del documento con `figcraft-cli run` (node.get) e controlla, frame per frame:
  REQUISITI (FAIL)  font mancanti · testo sotto 12 px · contrasto testo/fondo sotto WCAG 2.2
                    (4.5:1, o 3:1 per testo grande ≥ 24 px o ≥ 18.67 px bold) · elementi con
                    interazioni di prototipo sotto 24×24 px (WCAG 2.5.8)
  EURISTICHE (AVVISO) caratteri di default (Inter & co.) · testo corrente sotto 16 px nei frame mobili · target sotto 44×44 px nei
                    frame mobili · coordinate o dimensioni non intere · quasi-allineamenti tra
                    fratelli (0 < scarto < 1 px)
Il fondo di un testo è il primo antenato con riempimento solido opaco: sfumature, immagini e
trasparenze non sono valutate (segnalate come NON VERIFICATO). Le misure non giudicano la
qualità del design: quella si guarda sui render (render.py) e si critica.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "color-system/scripts"))
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from color import apca_lc, parse_hex, wcag_ratio  # noqa: E402


def run_steps(path, steps):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(steps, fh)
        script = fh.name
    try:
        r = subprocess.run(["figcraft-cli", "run", script, "--in", str(path)], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(script)
    out = []
    for line in r.stdout.splitlines():
        if line.startswith("{"):
            out.append(json.loads(line))
    if r.returncode and not out:
        sys.exit(f"figcraft-cli run: {r.stderr.strip()[:400]}")
    return out


def solid(fills):
    for f in reversed(fills or []):
        if f.get("type") == "solid" and f.get("visible", True) is not False and (f.get("opacity", 1) or 1) >= 0.999:
            c = f.get("color", "")
            if isinstance(c, str) and len(c) == 7:
                return c
    return None


def complex_fill(fills):
    return any(f.get("type") != "solid" or (f.get("opacity", 1) or 1) < 0.999 for f in (fills or []))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file")
    p.add_argument("--mobile-max", type=float, default=480, help="larghezza massima di un frame considerato mobile")
    p.add_argument("--record-by")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    path = Path(a.file).resolve()
    info = json.loads(subprocess.run(["figcraft-cli", "info", str(path), "--json"], capture_output=True, text=True).stdout)

    fails, warns, unverified = [], [], []
    for f in info.get("missingFonts") or []:
        fails.append(f"font mancante: {f} (il design è reso con un ripiego)")

    # Visita dell'albero a livelli: una esecuzione di figcraft-cli per livello.
    pages = [pg["id"] for pg in info.get("pages", [])]
    nodes, parent_of, frame_of = {}, {}, {}
    level = pages
    while level:
        results = run_steps(path, [{"command": "node.get", "params": {"id": i}} for i in level])
        nxt = []
        for res in results:
            n = res.get("result") or {}
            if "id" not in n:
                continue
            nodes[n["id"]] = n
            for c in n.get("children") or []:
                parent_of[c["id"]] = n["id"]
                frame_of[c["id"]] = c["id"] if n.get("type") == "PAGE" else frame_of.get(n["id"], n["id"])
                nodes.setdefault(c["id"], c)
                if c.get("childCount") or c.get("children"):
                    nxt.append(c["id"])
        level = [i for i in nxt if "children" not in nodes.get(i, {}) or not nodes[i]["children"]] if nxt else []
        level = list(dict.fromkeys(level))

    def frame_width(nid):
        top = frame_of.get(nid, nid)
        return (nodes.get(top) or {}).get("width") or 0

    def where(n):
        top = nodes.get(frame_of.get(n["id"], n["id"]), {})
        return f"«{top.get('name', '?')}» › {n.get('name', n.get('type'))} (id {n['id']})"

    texts = targets = 0
    families = set()
    for nid, n in nodes.items():
        if n.get("type") == "PAGE":
            continue
        mobile = frame_width(nid) and frame_width(nid) <= a.mobile_max
        for key in ("x", "y", "width", "height"):
            v = n.get(key)
            if isinstance(v, (int, float)) and abs(v - round(v)) > 0.01 and n.get("type") != "TEXT":
                warns.append(f"{where(n)}: {key} non intero ({v})")
                break
        if n.get("type") == "TEXT":
            texts += 1
            if n.get("fontFamily"):
                families.add(n["fontFamily"])
            size = n.get("fontSize") or 0
            bold = str(n.get("fontStyle", "")).lower() in ("bold", "black", "extrabold", "semibold", "heavy")
            if size and size < 12:
                fails.append(f"{where(n)}: testo a {size:g} px (< 12)")
            elif mobile and size < 16 and len(n.get("characters", "")) > 40:
                warns.append(f"{where(n)}: testo corrente a {size:g} px in un frame mobile (< 16)")
            fg = solid(n.get("fills"))
            anc, bg, blocked = parent_of.get(nid), None, False
            while anc is not None and bg is None:
                an = nodes.get(anc, {})
                if complex_fill(an.get("fills")) and not solid(an.get("fills")):
                    blocked = True
                    break
                bg = solid(an.get("fills"))
                anc = parent_of.get(anc)
            if fg and bg:
                ratio = wcag_ratio(parse_hex(fg), parse_hex(bg))
                lc = apca_lc(parse_hex(fg), parse_hex(bg))
                large = size >= 24 or (bold and size >= 18.67)
                need = 3.0 if large else 4.5
                if ratio + 1e-9 < need:
                    fails.append(f"{where(n)}: contrasto {ratio:.2f}:1 (APCA {lc:.0f}) {fg} su {bg}, serve {need}:1")
            else:
                unverified.append(f"{where(n)}: contrasto non verificabile (fondo con sfumatura, immagine o trasparenza)"
                                  if blocked else f"{where(n)}: contrasto non verificabile (nessun fondo solido)")
        if n.get("interactions"):
            targets += 1
            w, h = n.get("width") or 0, n.get("height") or 0
            if w < 24 or h < 24:
                fails.append(f"{where(n)}: elemento interattivo {w:g}×{h:g} px (< 24×24, WCAG 2.5.8)")
            elif mobile and (w < 44 or h < 44):
                warns.append(f"{where(n)}: target touch {w:g}×{h:g} px (< 44×44 consigliati)")

    # Caratteri di default (FigCraft usa Inter quando non se ne sceglie uno): scelta da motivare.
    defaults = {"inter", "roboto", "arial", "helvetica", "open sans", "montserrat", "poppins", "lato"}
    for fam in sorted(families):
        if fam.lower() in defaults:
            warns.append(f"carattere di default '{fam}': scegli il carattere per il brand (type-system) o motiva la scelta")

    # Quasi-allineamenti tra fratelli.
    siblings = {}
    for nid, pid in parent_of.items():
        siblings.setdefault(pid, []).append(nodes.get(nid, {}))
    for pid, kids in siblings.items():
        for axis in ("x", "y"):
            vals = sorted({round(k.get(axis), 3) for k in kids if isinstance(k.get(axis), (int, float))})
            for v1, v2 in zip(vals, vals[1:]):
                if 0 < v2 - v1 < 1:
                    warns.append(f"«{nodes.get(pid, {}).get('name', pid)}»: quasi-allineamento su {axis} ({v1} / {v2})")

    frames = [f for pg in info.get("pages", []) for f in pg.get("frames", [])]
    report = {"file": a.file, "frames": [(f["name"], f["width"], f["height"]) for f in frames], "texts": texts,
              "interactive": targets, "fail": fails, "warn": warns, "not_verified": unverified,
              "result": "FAIL" if fails else "PASS"}
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{a.file}: {len(frames)} frame, {texts} testi, {targets} elementi interattivi")
        for f in frames:
            print(f"  frame «{f['name']}» {f['width']:g}×{f['height']:g}")
        for x in fails:
            print(f"  FAIL   {x}")
        for x in warns:
            print(f"  AVVISO {x}")
        for x in unverified:
            print(f"  NON VERIFICATO {x}")
        print(report["result"] + " (requisiti misurabili; la qualità del design si giudica guardando i render)")
    if a.record_by:
        import evidence
        evidence.record_auto(a.file, "design_audit", report["result"], a.record_by,
                             note=f"{len(fails)} fail, {len(warns)} avvisi, {len(unverified)} non verificati")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
