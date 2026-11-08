#!/usr/bin/env python3
"""Audit geometrico di un SVG di logo: nodi, quasi-allineamenti, segmenti minuscoli,
e attributi che non appartengono a un master di consegna (transform, stroke, testo,
gradienti, filtri, maschere, opacità).

Un quasi-allineamento (due punti a distanza 0 < d < tolleranza su x o y) è quasi
sempre un errore: o i punti sono allineati o sono chiaramente diversi.
Solo libreria standard.  Uso: svg_audit.py logo.svg [--tol 0.25] [--json]
"""
import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
TOKEN = re.compile(rf"([MmLlHhVvCcSsQqTtAaZz])|({NUM})")
ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_path(d):
    """Restituisce (anchors, controls, subpaths): coordinate assolute."""
    tokens = TOKEN.findall(d)
    anchors, controls = [], []
    cx = cy = sx = sy = 0.0
    cmd, i, subpaths = None, 0, 0
    nums = []

    def flush():
        nonlocal cx, cy, sx, sy, cmd, subpaths
        up = cmd.upper()
        rel = cmd.islower()
        n = ARGC[up]
        if n == 0:
            cx, cy = sx, sy
            return
        if len(nums) % n:
            raise ValueError(f"argomenti incompleti per {cmd}")
        for k in range(0, len(nums), n):
            a = nums[k:k + n]
            ox, oy = (cx, cy) if rel else (0.0, 0.0)
            if up == "M":
                cx, cy = a[0] + ox, a[1] + oy
                if k == 0:
                    sx, sy = cx, cy
                    subpaths += 1
            elif up == "L" or up == "T":
                cx, cy = a[0] + ox, a[1] + oy
            elif up == "H":
                cx = a[0] + (cx if rel else 0.0)
            elif up == "V":
                cy = a[0] + (cy if rel else 0.0)
            elif up == "C":
                controls.extend([(a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)])
                cx, cy = a[4] + ox, a[5] + oy
            elif up in ("S", "Q"):
                controls.append((a[0] + ox, a[1] + oy))
                cx, cy = a[2] + ox, a[3] + oy
            elif up == "A":
                cx, cy = a[5] + ox, a[6] + oy
            anchors.append((cx, cy))

    for c, n in tokens:
        if c:
            if cmd is not None:
                flush()
            cmd, nums = c, []
            if c in "Zz":
                flush()
                cmd = None
        else:
            if cmd is None:
                raise ValueError("numero prima di un comando")
            nums.append(float(n))
            # Coppie implicite dopo M diventano L.
    if cmd is not None:
        flush()
    return anchors, controls, subpaths


def shape_points(el):
    tag = local(el.tag)
    f = lambda k: float(el.get(k, 0) or 0)
    if tag == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], []
    if tag in ("circle", "ellipse"):
        cx, cy = f("cx"), f("cy")
        rx = f("r") if tag == "circle" else f("rx")
        ry = f("r") if tag == "circle" else f("ry")
        return [(cx - rx, cy), (cx + rx, cy), (cx, cy - ry), (cx, cy + ry)], []
    if tag == "line":
        return [(f("x1"), f("y1")), (f("x2"), f("y2"))], []
    if tag in ("polyline", "polygon"):
        vals = [float(v) for v in re.findall(NUM, el.get("points", ""))]
        return list(zip(vals[::2], vals[1::2])), []
    return None


GRAPHICS = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan", "textPath", "use")


def own_stroke(el):
    stroke = el.get("stroke") or (re.search(r"stroke\s*:\s*([^;]+)", el.get("style", "")) or [None, None])[1]
    return stroke.strip() if stroke else None


def effective_strokes(root):
    """Maps each element to its stroke: its own value, else the one inherited from its parent."""
    result = {}

    def walk(el, parent):
        stroke = own_stroke(el)
        if stroke is None or stroke == "inherit":
            stroke = parent
        result[el] = stroke
        for child in el:
            walk(child, stroke)

    walk(root, None)
    return result


def near_misses(values, tol):
    vals = sorted(set(round(v, 6) for v in values))
    hits = []
    for a, b in zip(vals, vals[1:]):
        if 0 < b - a < tol:
            hits.append((a, b))
    return hits


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("svg")
    p.add_argument("--tol", type=float, help="tolleranza in unità utente (default: 0.2%% del lato del viewBox)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        root = ET.parse(args.svg).getroot()
    except (OSError, ET.ParseError) as exc:
        sys.exit(f"ERROR {args.svg}: {exc}")

    vb = [float(v) for v in re.findall(NUM, root.get("viewBox", ""))]
    side = max(vb[2], vb[3]) if len(vb) == 4 else None
    tol = args.tol if args.tol is not None else (side * 0.002 if side else 0.25)

    report = {"file": args.svg, "viewBox": vb or None, "tolerance": round(tol, 4), "shapes": [],
              "warnings": [], "near_miss_x": [], "near_miss_y": [], "tiny_segments": []}
    if not vb:
        report["warnings"].append("viewBox assente: la scala dell'SVG dipende da width/height")
    all_x, all_y = [], []
    flagged = set()
    strokes = effective_strokes(root)

    for el in root.iter():
        tag = local(el.tag)
        for attr, msg in (("transform", "transform non applicato"), ("opacity", "opacità"),
                          ("mask", "maschera"), ("filter", "filtro"), ("clip-path", "clip-path")):
            if el.get(attr) is not None:
                flagged.add(f"{msg} su <{tag} id={el.get('id', '?')}>")
        stroke = own_stroke(el)
        if stroke == "inherit":
            stroke = None
        if stroke and stroke != "none" and tag not in ("svg", "g"):
            flagged.add(f"tratto non espanso su <{tag} id={el.get('id', '?')}> (stroke={stroke})")
        elif not stroke and tag in GRAPHICS and strokes[el] and strokes[el] != "none":
            # inherited from an ancestor
            flagged.add(f"tratto non espanso su <{tag} id={el.get('id', '?')}> (stroke={strokes[el]})")
        if tag == "style":
            flagged.add("foglio di stile <style>: stili non verificabili, scriverli come attributi sugli elementi")
        if tag in ("text", "tspan"):
            flagged.add("testo vivo: nel deliverable convertire in tracciati, conservare il master con testo")
        if tag in ("linearGradient", "radialGradient"):
            flagged.add("gradiente: il marchio primario deve funzionare in un colore pieno")
        if tag in ("image",):
            flagged.add("immagine raster incorporata")

        if tag == "path":
            try:
                anchors, controls, subs = parse_path(el.get("d", ""))
            except ValueError as exc:
                report["warnings"].append(f"path {el.get('id', '?')}: {exc}")
                continue
        else:
            res = shape_points(el)
            if res is None:
                continue
            (anchors, controls), subs = res, 1
        pts = anchors + controls
        if not pts:
            continue
        xs, ys = [p_[0] for p_ in pts], [p_[1] for p_ in pts]
        report["shapes"].append({"tag": tag, "id": el.get("id"), "nodes": len(anchors), "subpaths": subs,
                                 "bbox_approx": [round(min(xs), 3), round(min(ys), 3),
                                                 round(max(xs), 3), round(max(ys), 3)]})
        all_x += [a[0] for a in anchors]
        all_y += [a[1] for a in anchors]
        for a, b in zip(anchors, anchors[1:]):
            d = math.dist(a, b)
            if 0 < d < tol:
                report["tiny_segments"].append({"id": el.get("id"), "from": [round(v, 4) for v in a],
                                                "to": [round(v, 4) for v in b], "length": round(d, 5)})

    report["warnings"] += sorted(flagged)
    report["near_miss_x"] = [[round(a, 4), round(b, 4)] for a, b in near_misses(all_x, tol)]
    report["near_miss_y"] = [[round(a, 4), round(b, 4)] for a, b in near_misses(all_y, tol)]
    report["total_nodes"] = sum(s["nodes"] for s in report["shapes"])

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{args.svg}: {len(report['shapes'])} forme, {report['total_nodes']} nodi, tolleranza {tol:.4g}")
        for s in report["shapes"]:
            print(f"  <{s['tag']}> {s['id'] or ''} nodi={s['nodes']} sottotracciati={s['subpaths']} bbox≈{s['bbox_approx']} (archi: solo estremi)")
        for key, label in (("near_miss_x", "quasi-allineamenti x"), ("near_miss_y", "quasi-allineamenti y")):
            if report[key]:
                print(f"  {label}: {report[key][:12]}" + (" …" if len(report[key]) > 12 else ""))
        if report["tiny_segments"]:
            print(f"  segmenti minuscoli: {len(report['tiny_segments'])}, es. {report['tiny_segments'][:3]}")
        for w in report["warnings"]:
            print(f"  AVVISO {w}")
    issues = report["near_miss_x"] or report["near_miss_y"] or report["tiny_segments"] or report["warnings"]
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
