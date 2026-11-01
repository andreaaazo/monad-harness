#!/usr/bin/env python3
"""Libreria di caratteri dello studio: catalogo Google Fonts (licenze aperte), ricerca con filtri,
download nel progetto con licenza registrata, specimen sui testi veri del cliente.

Scegliere tra i caratteri installati sulla macchina porta sempre agli stessi (Inter & co.).
Questo strumento allarga la scelta a ~1900 famiglie e permette di escludere le più popolari.

  font_library.py search [--category serif|sans|display|handwriting|mono] [--subset latin-ext]
                         [--min-styles 4] [--variable] [--avoid-popular 60] [--query testo] [--limit 30]
  font_library.py fetch "Fraunces" "Familjen Grotesk" [--install]     # → work/fonts/<slug>/ + LICENSE-RECORD.json
  font_library.py specimen "Fraunces" "Familjen Grotesk" --text "Fisio Lago" --text2 "Fisioterapia sportiva" \
                           [--out work/proofs/specimen]               # HTML + PNG renderizzati: guardali con Read

Fonte: https://fonts.google.com/metadata/fonts e il repository github.com/google/fonts.
I caratteri commerciali (fonderie) non sono qui: si propongono al cliente con licenza da acquistare.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[4])
HOME_DIR = Path(os.environ.get("DESIGN_AGENCY_HOME", Path.home() / ".local/share/design-agency"))
CACHE = HOME_DIR / "cache/google-fonts-metadata.json"
SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
CATS = {"serif": "Serif", "sans": "Sans Serif", "display": "Display", "handwriting": "Handwriting", "mono": "Monospace"}
UA = {"User-Agent": "design-agency-font-library"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def catalog():
    if CACHE.exists() and time.time() - CACHE.stat().st_mtime < 7 * 86400:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    raw = get("https://fonts.google.com/metadata/fonts").decode("utf-8")
    data = json.loads(raw[raw.find("{"):])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    return data


def slug(family):
    return re.sub(r"[^a-z0-9]", "", family.lower())


def cmd_search(a):
    fams = catalog()["familyMetadataList"]
    # "popularity" è un rango (1 = più usata) con valori ripetuti tra famiglie: si filtra sul valore.
    popular = {f["family"] for f in fams if f.get("popularity", 10 ** 6) <= a.avoid_popular} if a.avoid_popular else set()
    out = []
    for f in fams:
        if a.category and f["category"] != CATS[a.category]:
            continue
        if a.subset and a.subset not in f.get("subsets", []):
            continue
        if f["family"] in popular or f.get("isNoto") and not a.noto:
            continue
        if a.variable and not f.get("axes"):
            continue
        if len(f.get("fonts", {})) < a.min_styles:
            continue
        if a.query and a.query.lower() not in (f["family"] + " " + " ".join(f.get("designers", []))).lower():
            continue
        out.append(f)
    out.sort(key=lambda f: f.get("popularity", 10 ** 6))
    print(f"{len(out)} famiglie (escluse {len(popular)} con rango di popolarità ≤ {a.avoid_popular})" if a.avoid_popular else f"{len(out)} famiglie")
    for f in out[: a.limit]:
        axes = ",".join(x["tag"] for x in f.get("axes", [])) or "-"
        print(f"  {f['family']:28} {f['category']:12} stili {len(f.get('fonts', {})):2}  assi {axes:16} "
              f"pop #{f.get('popularity')}  {', '.join(f.get('designers', [])[:2])}")


def list_dir(path):
    data = json.loads(get(f"https://api.github.com/repos/google/fonts/contents/{path}"))
    return data if isinstance(data, list) else []


def cmd_fetch(a):
    fams = {f["family"]: f for f in catalog()["familyMetadataList"]}
    for family in a.families:
        if family not in fams:
            print(f"NON NEL CATALOGO: {family}")
            continue
        s = slug(family)
        entries, lic_dir = [], None
        for d in ("ofl", "apache", "ufl"):
            try:
                entries = list_dir(f"{d}/{s}")
            except Exception:
                entries = []
            if entries:
                lic_dir = d
                break
        if not entries:
            print(f"NON TROVATO NEL REPOSITORY: {family} ({s})")
            continue
        dest = ROOT / "work/fonts" / s
        dest.mkdir(parents=True, exist_ok=True)
        files = []
        for e in entries:
            if e["type"] == "file" and (e["name"].endswith((".ttf", ".otf")) or e["name"] in ("OFL.txt", "LICENSE.txt", "UFL.txt", "METADATA.pb")):
                (dest / e["name"]).write_bytes(get(e["download_url"]))
                files.append(e["name"])
        if not any(n.endswith((".ttf", ".otf")) for n in files):
            # Alcune famiglie tengono i file in sottocartelle (es. static/).
            for e in entries:
                if e["type"] == "dir":
                    for sub in list_dir(e["path"]):
                        if sub["name"].endswith((".ttf", ".otf")):
                            (dest / sub["name"]).write_bytes(get(sub["download_url"]))
                            files.append(sub["name"])
        license_name = {"ofl": "SIL Open Font License 1.1", "apache": "Apache License 2.0", "ufl": "Ubuntu Font Licence 1.0"}[lic_dir]
        record = {"family": family, "license": license_name, "source": f"https://github.com/google/fonts/tree/main/{lic_dir}/{s}",
                  "catalog": "https://fonts.google.com/metadata/fonts", "fetched": str(date.today()), "files": files,
                  "designers": fams[family].get("designers"), "subsets": fams[family].get("subsets"),
                  "note": "Licenza aperta: uso commerciale, web, app e logo consentiti; verificare le condizioni di "
                          "ridistribuzione e il divieto di vendere il font da solo."}
        (dest / "LICENSE-RECORD.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"SCARICATO {family} → {dest.relative_to(ROOT)} ({len(files)} file, {license_name})")
        if a.install:
            target = Path.home() / ".local/share/fonts/design-agency" / s
            target.mkdir(parents=True, exist_ok=True)
            for n in files:
                if n.endswith((".ttf", ".otf")):
                    shutil.copy(dest / n, target / n)
            subprocess.run(["fc-cache", "-f", str(target)], capture_output=True)
            print(f"  installato per i renderer di sistema: {target}")


def cmd_specimen(a):
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    faces, blocks = [], []
    for family in a.families:
        d = ROOT / "work/fonts" / slug(family)
        files = sorted(p for p in d.glob("*") if p.suffix in (".ttf", ".otf")) if d.exists() else []
        if not files:
            print(f"{family}: non scaricato (font_library.py fetch \"{family}\")")
            continue
        for i, f in enumerate(files):
            italic = "italic" if "Italic" in f.name else "normal"
            weight = "100 900" if "[" in f.name else str(next((w for k, w in (("Thin", 100), ("ExtraLight", 200), ("Light", 300),
                     ("Medium", 500), ("SemiBold", 600), ("ExtraBold", 800), ("Bold", 700), ("Black", 900)) if k in f.name), 400))
            faces.append(f"@font-face{{font-family:'S-{slug(family)}';src:url('{f.resolve().as_uri()}');"
                         f"font-weight:{weight};font-style:{italic};}}")
        lic = json.loads((d / "LICENSE-RECORD.json").read_text()).get("license", "?") if (d / "LICENSE-RECORD.json").exists() else "?"
        fam = f"'S-{slug(family)}'"
        blocks.append(f"""<section><div class=meta>{family} · {lic}</div>
<div style="font-family:{fam};font-weight:700;font-size:96px;line-height:1">{a.text}</div>
<div style="font-family:{fam};font-weight:400;font-size:36px;margin-top:12px">{a.text2}</div>
<div style="font-family:{fam};font-weight:400;font-size:17px;line-height:1.5;max-width:62ch;margin-top:16px">{a.body}</div>
<div style="font-family:{fam};font-size:22px;margin-top:10px">àèéìòù ÄÖÜß „Grüezi“ «Lugano» 0123456789 — 24°</div>
<div style="font-family:{fam};font-size:12px;margin-top:6px">{a.text2} · {a.text} · 12 px</div></section>""")
    html = out / "specimen.html"
    html.write_text(f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Specimen</title>
<style>{''.join(faces)} body{{margin:0;padding:48px;background:#fbfaf7;color:#16161a;font-family:serif}}
section{{padding:32px 0;border-bottom:1px solid #ddd}} .meta{{font:13px monospace;color:#666;margin-bottom:12px}}</style>
</head><body>{''.join(blocks)}</body></html>""", encoding="utf-8")
    r = subprocess.run([str(SCRIPTS / "py"), str(SCRIPTS / "render.py"), str(html), "--out", str(out)],
                       capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT)))
    print(r.stdout.strip() or r.stderr.strip())
    print("Guarda lo specimen con Read: nome, descrittore, testo corrente, accenti e cifre, corpo minimo.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--category", choices=list(CATS))
    s.add_argument("--subset")
    s.add_argument("--min-styles", type=int, default=1)
    s.add_argument("--variable", action="store_true")
    s.add_argument("--avoid-popular", type=int, default=100, help="escludi le famiglie con rango di popolarità ≤ N (0 = nessuna)")
    s.add_argument("--noto", action="store_true", help="includi le famiglie Noto")
    s.add_argument("--query")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("fetch")
    s.add_argument("families", nargs="+")
    s.add_argument("--install", action="store_true", help="copia anche in ~/.local/share/fonts per i renderer SVG")
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("specimen")
    s.add_argument("families", nargs="+")
    s.add_argument("--text", required=True)
    s.add_argument("--text2", default="")
    s.add_argument("--body", default="Testo corrente di prova: una frase reale del cliente mostra ritmo, colore e leggibilità meglio di qualsiasi pangramma.")
    s.add_argument("--out", default="work/proofs/specimen")
    s.set_defaults(fn=cmd_specimen)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
