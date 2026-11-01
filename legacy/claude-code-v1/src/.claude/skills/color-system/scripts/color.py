#!/usr/bin/env python3
"""Strumenti colore dello studio: OKLCH, rampe in gamut sRGB, contrasto APCA e WCAG 2.

Solo libreria standard. Esempi:
  color.py info "#B184FF"
  color.py contrast "#B184FF" "#FEFCFF"          # testo, sfondo
  color.py ramp --hue 290 --chroma 0.16 --lightness 0.97,0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2
  color.py matrix palette.json                  # {"text": {...}, "background": {...}}
"""
import argparse
import json
import math
import sys

# --- sRGB <-> OKLab (Ottosson 2020) -----------------------------------------


def parse_hex(value):
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(f"colore esadecimale non valido: {value}")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def linear_rgb_to_oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_linear_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def hex_to_oklch(value):
    L, a, b = linear_rgb_to_oklab(*(srgb_to_linear(c) for c in parse_hex(value)))
    C = math.hypot(a, b)
    H = math.degrees(math.atan2(b, a)) % 360 if C > 1e-4 else 0.0
    return L, C, H


def oklch_to_linear_rgb(L, C, H):
    h = math.radians(H)
    return oklab_to_linear_rgb(L, C * math.cos(h), C * math.sin(h))


def in_gamut(lin, eps=1e-6):
    return all(-eps <= c <= 1 + eps for c in lin)


def oklch_to_srgb_mapped(L, C, H):
    """Riduce la croma a L e H costanti finché il colore entra in sRGB.

    Bisezione sulla croma: preserva tinta e chiarezza, che sono le proprietà
    su cui la rampa è costruita. Restituisce (rgb_gamma, croma_effettiva, ridotta?)."""
    if in_gamut(oklch_to_linear_rgb(L, C, H)):
        return tuple(linear_to_srgb(max(0.0, min(1.0, c))) for c in oklch_to_linear_rgb(L, C, H)), C, False
    lo, hi = 0.0, C
    for _ in range(40):
        mid = (lo + hi) / 2
        if in_gamut(oklch_to_linear_rgb(L, mid, H)):
            lo = mid
        else:
            hi = mid
    lin = oklch_to_linear_rgb(L, lo, H)
    return tuple(linear_to_srgb(max(0.0, min(1.0, c))) for c in lin), lo, True


def max_chroma(L, H):
    lo, hi = 0.0, 0.5
    for _ in range(40):
        mid = (lo + hi) / 2
        if in_gamut(oklch_to_linear_rgb(L, mid, H)):
            lo = mid
        else:
            hi = mid
    return lo


# --- Contrasto -------------------------------------------------------------------


def wcag_luminance(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_ratio(fg, bg):
    a, b = wcag_luminance(fg), wcag_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def apca_lc(text, background):
    """APCA-W3 0.0.98G-4g (Myndex). Positivo: testo scuro su chiaro; negativo: inverso."""
    def y(rgb):
        r, g, b = rgb
        return 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4

    def clamp_black(v):
        return v if v > 0.022 else v + (0.022 - v) ** 1.414

    t, b = clamp_black(y(text)), clamp_black(y(background))
    if abs(b - t) < 0.0005:
        return 0.0
    if b > t:
        sapc = (b ** 0.56 - t ** 0.57) * 1.14
        out = 0.0 if sapc < 0.1 else sapc - 0.027
    else:
        sapc = (b ** 0.65 - t ** 0.62) * 1.14
        out = 0.0 if sapc > -0.1 else sapc + 0.027
    return out * 100


def wcag_verdict(ratio):
    if ratio >= 7:
        return "AAA testo"
    if ratio >= 4.5:
        return "AA testo"
    if ratio >= 3:
        return "AA testo grande / non-testo"
    return "sotto 3:1"


def apca_hint(lc):
    a = abs(lc)
    # Livelli indicativi della guida APCA "bronze"; la soglia reale dipende da corpo e peso.
    if a >= 90:
        return "testo corrente, anche sottile"
    if a >= 75:
        return "testo corrente"
    if a >= 60:
        return "testo di lettura ≥ ~16px normale"
    if a >= 45:
        return "titoli/testo grande"
    if a >= 30:
        return "testo non essenziale, segni grafici"
    if a >= 15:
        return "solo elementi non testuali grandi"
    return "insufficiente"


# --- Comandi ----------------------------------------------------------------------


def cmd_info(args):
    rows = []
    for value in args.colors:
        rgb = parse_hex(value)
        L, C, H = hex_to_oklch(value)
        rows.append({
            "hex": to_hex(rgb),
            "oklch": f"oklch({L * 100:.2f}% {C:.4f} {H:.2f})",
            "rgb255": [round(c * 255) for c in rgb],
            "wcag_luminance": round(wcag_luminance(rgb), 5),
            "max_chroma_at_L_H": round(max_chroma(L, H), 4),
        })
    emit(rows, args.json)


def cmd_contrast(args):
    fg, bg = parse_hex(args.text), parse_hex(args.background)
    lc, ratio = apca_lc(fg, bg), wcag_ratio(fg, bg)
    emit([{
        "text": to_hex(fg), "background": to_hex(bg),
        "apca_lc": round(lc, 1), "apca_use": apca_hint(lc),
        "wcag_ratio": round(ratio, 2), "wcag": wcag_verdict(ratio),
    }], args.json)


def cmd_ramp(args):
    lightness = [float(v) for v in args.lightness.split(",")]
    names = args.names.split(",") if args.names else [str((i + 1) * 100) for i in range(len(lightness))]
    if len(names) != len(lightness):
        sys.exit("--names deve avere tanti elementi quanti --lightness")
    white, black = (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)
    rows = []
    for name, L in zip(names, lightness):
        C = args.chroma
        if args.chroma_curve == "taper":
            # Croma piena al centro, ridotta agli estremi chiari e scuri, dove sRGB ne contiene poca.
            C = args.chroma * max(0.15, 1 - abs(L - args.peak) / max(args.peak, 1 - args.peak)) ** 0.8
        rgb, c_eff, clipped = oklch_to_srgb_mapped(L, C, args.hue)
        rows.append({
            "name": name, "hex": to_hex(rgb),
            "oklch": f"oklch({L * 100:.1f}% {c_eff:.4f} {args.hue:.1f})",
            "chroma_requested": round(C, 4), "gamut_mapped": clipped,
            "apca_on_white": round(apca_lc(rgb, white), 1),
            "apca_white_on": round(apca_lc(white, rgb), 1),
            "apca_on_black": round(apca_lc(rgb, black), 1),
            "wcag_vs_white": round(wcag_ratio(rgb, white), 2),
            "wcag_vs_black": round(wcag_ratio(rgb, black), 2),
        })
    emit(rows, args.json)


def cmd_matrix(args):
    with open(args.palette, encoding="utf-8") as fh:
        data = json.load(fh)
    texts = data.get("text") or data.get("foreground")
    backs = data.get("background")
    if not isinstance(texts, dict) or not isinstance(backs, dict):
        sys.exit('palette: atteso {"text": {nome: hex}, "background": {nome: hex}}')
    rows = []
    for tn, tv in texts.items():
        for bn, bv in backs.items():
            fg, bg = parse_hex(tv), parse_hex(bv)
            lc, ratio = apca_lc(fg, bg), wcag_ratio(fg, bg)
            rows.append({"text": f"{tn} {to_hex(fg)}", "background": f"{bn} {to_hex(bg)}",
                         "apca_lc": round(lc, 1), "apca_use": apca_hint(lc),
                         "wcag_ratio": round(ratio, 2), "wcag": wcag_verdict(ratio)})
    emit(rows, args.json)


def cmd_cvd(args):
    """Distanza percepita (ΔE OK) tra coppie di colori sotto simulazione di daltonismo."""
    try:
        from coloraide import Color
    except ImportError:
        sys.exit("coloraide mancante: eseguire con .claude/scripts/py dopo setup_tools.sh")
    with open(args.palette, encoding="utf-8") as fh:
        data = json.load(fh)
    colors = data.get("pairs") or data
    pairs = colors if isinstance(colors, list) else [(a, b) for i, a in enumerate(colors) for b in list(colors)[i + 1:]]
    lookup = colors if isinstance(colors, dict) else {}
    rows = []
    for a_name, b_name in pairs:
        a_hex, b_hex = lookup.get(a_name, a_name), lookup.get(b_name, b_name)
        row = {"a": f"{a_name} {a_hex}", "b": f"{b_name} {b_hex}",
               "dE_ok": round(Color(a_hex).delta_e(Color(b_hex), method="ok"), 4)}
        worst = row["dE_ok"]
        for kind in ("protan", "deutan", "tritan"):
            d = Color(a_hex).filter(kind).delta_e(Color(b_hex).filter(kind), method="ok")
            row[kind] = round(d, 4)
            worst = min(worst, d)
        row["result"] = "OK" if worst >= args.min_de else "CONFONDIBILE"
        rows.append(row)
    emit(rows, args.json)


def emit(rows, as_json):
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        return
    keys = list(rows[0].keys())
    widths = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in keys}
    print("  ".join(k.ljust(widths[k]) for k in keys))
    for r in rows:
        print("  ".join(str(r[k]).ljust(widths[k]) for k in keys))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="output JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="OKLCH, luminanza e croma massima in sRGB")
    s.add_argument("colors", nargs="+")
    s.set_defaults(fn=cmd_info)

    s = sub.add_parser("contrast", help="APCA Lc e rapporto WCAG 2 (testo, sfondo)")
    s.add_argument("text")
    s.add_argument("background")
    s.set_defaults(fn=cmd_contrast)

    s = sub.add_parser("ramp", help="rampa a tinta costante con L esplicite, mappata in sRGB")
    s.add_argument("--hue", type=float, required=True, help="tinta OKLCH in gradi")
    s.add_argument("--chroma", type=float, required=True, help="croma OKLCH di riferimento")
    s.add_argument("--lightness", required=True, help="L OKLCH 0–1 separate da virgola")
    s.add_argument("--names", help="nomi dei passi separati da virgola")
    s.add_argument("--chroma-curve", choices=["flat", "taper"], default="taper")
    s.add_argument("--peak", type=float, default=0.62, help="L con croma piena (taper)")
    s.set_defaults(fn=cmd_ramp)

    s = sub.add_parser("matrix", help="contrasto di tutte le coppie testo×sfondo da un JSON")
    s.add_argument("palette")
    s.set_defaults(fn=cmd_matrix)

    s = sub.add_parser("cvd", help="coppie distinguibili con protanopia, deuteranopia, tritanopia (coloraide)")
    s.add_argument("palette", help='JSON {nome: hex} (tutte le coppie) o {"pairs": [[a, b], …]} con hex')
    s.add_argument("--min-de", type=float, default=0.1, help="ΔE OK minimo accettato (scelta dello studio)")
    s.set_defaults(fn=cmd_cvd)

    args = p.parse_args()
    try:
        args.fn(args)
    except ValueError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
