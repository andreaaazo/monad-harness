#!/usr/bin/env python3
"""Scala tipografica modulare con interlinea agganciata a una griglia di base.

Solo libreria standard. Esempi:
  type_scale.py --base 16 --ratio major-third --steps -2:6 --grid 4
  type_scale.py --base 16 --ratio 1.2 --max-base 18 --max-ratio 1.333 --viewport 360:1440 --css
  type_scale.py --base 17 --ratio perfect-fourth --names caption,small,body,lede,h4,h3,h2,h1,display --dtcg

Il rapporto è uno strumento di coerenza, non una legge: i passi estremi vanno
corretti a vista con contenuti reali e registrati come deviazioni.
"""
import argparse
import json
import math
import sys

RATIOS = {
    "minor-second": 16 / 15, "major-second": 9 / 8, "minor-third": 6 / 5,
    "major-third": 5 / 4, "perfect-fourth": 4 / 3, "augmented-fourth": math.sqrt(2),
    "perfect-fifth": 3 / 2, "golden": (1 + math.sqrt(5)) / 2,
}


def ratio_value(text):
    if text in RATIOS:
        return RATIOS[text]
    try:
        value = float(text)
    except ValueError:
        sys.exit(f"rapporto sconosciuto: {text} (usa un numero o {', '.join(RATIOS)})")
    if value <= 1:
        sys.exit("il rapporto deve essere > 1")
    return value


def line_height(size, base, top, lh_body, lh_display, grid):
    # Interlinea relativa che scende dal corpo testo ai titoli: i corpi grandi
    # hanno bisogno di meno spazio relativo tra le righe.
    t = 0.0 if top <= base else max(0.0, min(1.0, (size - base) / (top - base)))
    ratio = lh_body + (lh_display - lh_body) * t
    raw = size * ratio
    return math.ceil(raw / grid - 1e-9) * grid if grid else raw


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=float, required=True, help="corpo del testo base in px")
    p.add_argument("--ratio", required=True)
    p.add_argument("--steps", default="-2:6", help="intervallo di passi, es. -2:6")
    p.add_argument("--names", help="nomi dei passi, dal più piccolo al più grande")
    p.add_argument("--grid", type=float, default=4, help="griglia di base in px (0 = nessuna)")
    p.add_argument("--lh-body", type=float, default=1.5)
    p.add_argument("--lh-display", type=float, default=1.1)
    p.add_argument("--round", type=float, default=1, help="arrotonda i corpi a multipli di questo valore (0 = no)")
    p.add_argument("--max-base", type=float, help="corpo base al viewport massimo (scala fluida)")
    p.add_argument("--max-ratio", help="rapporto al viewport massimo (scala fluida)")
    p.add_argument("--viewport", default="360:1440", help="viewport min:max in px per clamp()")
    p.add_argument("--css", action="store_true", help="stampa custom properties CSS")
    p.add_argument("--dtcg", action="store_true", help="stampa token DTCG")
    args = p.parse_args()

    lo, hi = (int(v) for v in args.steps.split(":"))
    steps = list(range(lo, hi + 1))
    names = args.names.split(",") if args.names else [f"step-n{-s}" if s < 0 else f"step-{s}" for s in steps]
    if len(names) != len(steps):
        sys.exit(f"--names: attesi {len(steps)} nomi, ricevuti {len(names)}")

    r = ratio_value(args.ratio)
    fluid = args.max_base is not None
    r_max = ratio_value(args.max_ratio) if args.max_ratio else r
    vw_min, vw_max = (float(v) for v in args.viewport.split(":"))

    def size(base, ratio, step):
        value = base * ratio ** step
        return round(value / args.round) * args.round if args.round else value

    top = size(args.base, r, hi)
    rows = []
    for name, step in zip(names, steps):
        s_min = size(args.base, r, step)
        lh = line_height(s_min, args.base, top, args.lh_body, args.lh_display, args.grid)
        row = {"name": name, "step": step, "size_px": round(s_min, 2), "line_height_px": round(lh, 2),
               "line_height_ratio": round(lh / s_min, 3)}
        if fluid:
            s_max = size(args.max_base, r_max, step)
            slope = (s_max - s_min) / (vw_max - vw_min)
            intercept = s_min - slope * vw_min
            row["size_max_px"] = round(s_max, 2)
            row["clamp"] = (f"clamp({s_min / 16:.4g}rem, {intercept / 16:.4g}rem + {slope * 100:.4g}vw, {s_max / 16:.4g}rem)"
                            if s_max != s_min else f"{s_min / 16:.4g}rem")
        rows.append(row)

    if args.css:
        for row in rows:
            value = row.get("clamp", f"{row['size_px'] / 16:.4g}rem")
            print(f"--font-size-{row['name']}: {value};")
            print(f"--line-height-{row['name']}: {row['line_height_ratio']};")
        return
    if args.dtcg:
        tokens = {"font-size": {"$type": "dimension"}, "line-height": {"$type": "number"}}
        for row in rows:
            tokens["font-size"][row["name"]] = {"$value": {"value": row["size_px"], "unit": "px"}}
            tokens["line-height"][row["name"]] = {"$value": row["line_height_ratio"]}
        print(json.dumps(tokens, indent=2))
        return

    keys = list(rows[0].keys())
    widths = {k: max(len(k), *(len(str(r_[k])) for r_ in rows)) for k in keys}
    print(f"rapporto {r:.4f}" + (f" → {r_max:.4f} (fluido {vw_min:g}–{vw_max:g}px)" if fluid else "")
          + (f", griglia {args.grid:g}px" if args.grid else ""))
    print("  ".join(k.ljust(widths[k]) for k in keys))
    for row in rows:
        print("  ".join(str(row[k]).ljust(widths[k]) for k in keys))


if __name__ == "__main__":
    main()
