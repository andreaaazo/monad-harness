#!/usr/bin/env python3
"""Ispeziona un font: nomi, versione, licenza dichiarata, permessi di embedding, metriche,
copertura per lingua, feature OpenType, assi variabili; shaping reale di un campione.

  font_inspect.py Font.otf [--langs it,en,de,fr,es,pt,pl,cs,tr] [--sample "Testo del brand"] [--json]

La licenza dichiarata nel file (name ID 13/14) non sostituisce l'EULA della fonderia:
registrala e verificala. Usa il venv dello studio (.claude/scripts/py).
"""
import argparse
import json
import sys

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("fontTools mancante: bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

BASIC = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:;!?'\"()[]{}-–—/&@#%*+=€$"
LANGS = {
    "it": "àèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ«»“”‘’…",
    "en": "“”‘’…",
    "de": "äöüßÄÖÜẞ„“‚‘",
    "fr": "àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ«»",
    "es": "áéíñóúüÁÉÍÑÓÚÜ¿¡«»",
    "pt": "ãõáâàçéêíóôúÃÕÁÂÀÇÉÊÍÓÔÚ",
    "pl": "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”",
    "cs": "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ„“",
    "tr": "çğıİöşüÇĞÖŞÜ",
    "ro": "ăâîșțĂÂÎȘȚ„”",
    "hu": "áéíóöőúüűÁÉÍÓÖŐÚÜŰ„”",
    "hr": "čćđšžČĆĐŠŽ„“",
    "nl": "ëïéèĳĲ",
    "nordic": "åäöæøÅÄÖÆØ",
}
EMBEDDING = {0: "installabile", 2: "restricted (nessun embedding)", 4: "preview & print", 8: "editabile"}


def name(font, nid):
    rec = font["name"].getName(nid, 3, 1) or font["name"].getName(nid, 1, 0)
    return str(rec) if rec else None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("font")
    p.add_argument("--langs", default="it,en,de,fr,es,pt,pl,cs,tr")
    p.add_argument("--sample")
    p.add_argument("--index", type=int, default=0, help="indice in una collezione .ttc")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    font = TTFont(a.font, fontNumber=a.index, lazy=True)
    cmap = font.getBestCmap() or {}
    os2 = font["OS/2"] if "OS/2" in font else None
    head, hhea = font["head"], font["hhea"]
    upm = head.unitsPerEm

    info = {
        "family": name(font, 16) or name(font, 1), "style": name(font, 17) or name(font, 2),
        "full_name": name(font, 4), "version": name(font, 5), "manufacturer": name(font, 8),
        "designer": name(font, 9), "license": name(font, 13), "license_url": name(font, 14),
        "vendor": os2.achVendID if os2 else None, "glyphs": font["maxp"].numGlyphs, "units_per_em": upm,
    }
    if os2:
        fs = os2.fsType
        kind = EMBEDDING.get(fs & 0xE, f"bit {fs:#x}")
        info["embedding"] = kind + (" · no subsetting" if fs & 0x100 else "") + (" · bitmap only" if fs & 0x200 else "")
        info["weight_class"] = os2.usWeightClass
        info["metrics"] = {
            "x_height": getattr(os2, "sxHeight", None), "cap_height": getattr(os2, "sCapHeight", None),
            "typo_ascender": os2.sTypoAscender, "typo_descender": os2.sTypoDescender, "typo_line_gap": os2.sTypoLineGap,
            "win_ascent": os2.usWinAscent, "win_descent": os2.usWinDescent,
            "hhea_ascender": hhea.ascent, "hhea_descender": hhea.descent, "hhea_line_gap": hhea.lineGap,
            "use_typo_metrics": bool(os2.fsSelection & (1 << 7)),
        }
        if info["metrics"]["x_height"] and info["metrics"]["cap_height"]:
            info["metrics"]["x_to_cap"] = round(info["metrics"]["x_height"] / info["metrics"]["cap_height"], 3)

    coverage = {}
    for lang in [l.strip() for l in a.langs.split(",") if l.strip()]:
        chars = BASIC + LANGS.get(lang, "")
        missing = [c for c in dict.fromkeys(chars) if ord(c) not in cmap]
        coverage[lang] = "ok" if not missing else "MANCANO " + "".join(missing)
    info["coverage"] = coverage

    feats = set()
    for tag in ("GSUB", "GPOS"):
        if tag in font and font[tag].table.FeatureList:
            feats |= {r.FeatureTag for r in font[tag].table.FeatureList.FeatureRecord}
    info["features"] = sorted(feats)
    info["kerning"] = "kern" in feats or "kern" in font
    if "fvar" in font:
        info["axes"] = {ax.axisTag: [ax.minValue, ax.defaultValue, ax.maxValue] for ax in font["fvar"].axes}
        info["named_instances"] = len(font["fvar"].instances)

    warnings = []
    m = info.get("metrics", {})
    if m and not m.get("use_typo_metrics") and m.get("typo_ascender") != m.get("hhea_ascender"):
        warnings.append("metriche typo e hhea diverse senza USE_TYPO_METRICS: interlinea diversa tra sistemi")
    if os2 and (os2.fsType & 0xE) == 2:
        warnings.append("embedding restricted: non incorporabile in PDF/app senza licenza specifica")
    if not info["license"]:
        warnings.append("nessuna licenza dichiarata nel file: verificare l'EULA")
    if "tnum" not in feats:
        warnings.append("niente cifre tabellari (tnum): tabelle e dati non si allineano")
    info["warnings"] = warnings

    if a.sample:
        try:
            import uharfbuzz as hb
            blob = hb.Blob.from_file_path(a.font)
            hb_font = hb.Font(hb.Face(blob, a.index))
            buf = hb.Buffer()
            buf.add_str(a.sample)
            buf.guess_segment_properties()
            hb.shape(hb_font, buf, {"kern": True, "liga": True})
            notdef = sum(1 for g in buf.glyph_infos if g.codepoint == 0)
            width = sum(pos.x_advance for pos in buf.glyph_positions)
            info["sample"] = {"text": a.sample, "glyphs": len(buf.glyph_infos), "notdef": notdef,
                              "advance_em": round(width / upm, 3)}
        except ImportError:
            info["sample"] = "uharfbuzz assente"

    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    for k, v in info.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"  {kk}: {vv}")
        elif isinstance(v, list) and k == "warnings":
            for w in v:
                print(f"AVVISO {w}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
