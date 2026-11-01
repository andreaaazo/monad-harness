#!/usr/bin/env python3
"""Tavole di confronto dello sprint delle direzioni, anonime, con misura della diversità.

  direction_board.py check  [--apps work/directions/apps.json]   # completezza e formati di ogni direzione
  direction_board.py boards [--seed N]                            # tavole anonime per applicazione
  direction_board.py diversity                                    # quanto sono diverse davvero
  direction_board.py lint      [--record-by agente]               # scheda di ogni direzione: campi, cliché, licenze
  direction_board.py concepts  [--record-by agente]               # diversità di concept, caratteri, colori, leve
  direction_board.py reveal                                       # mappa X/Y/Z → A/B/C (dopo il giudizio)

apps.json (scritto con il brief pack) elenca le applicazioni comuni, uguali per tutte:
  {"apps": [{"id": "A1", "name": "Logo e lockup", "size": [1600, 1000]}, …]}
Ogni direzione consegna work/directions/<lettera>/apps/<id>.png alle dimensioni esatte,
e work/directions/<lettera>/direction.md con le sezioni obbligatorie.
"""
import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
    from skimage.metrics import structural_similarity
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[4])
DIRS = ROOT / "work/directions"
SECTIONS = ["Concept", "Composizione", "Tipografia", "Colore", "Linguaggio delle immagini", "Movimento",
            "Voce", "Fatti su cui si basa", "Rischi"]
BLIND = ROOT / ".agency/blind-map.json"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))


def compared_files():
    """Tutto ciò che il confronto ha letto: schede e applicazioni di ogni direzione e il brief pack."""
    files = [DIRS / "brief-pack.md"]
    for d in directions():
        files.append(DIRS / d / "direction.md")
        files += sorted((DIRS / d / "apps").glob("*.png"))
    return [str(f.relative_to(ROOT)) for f in files if f.exists()]


def record(a, check, ok, note, heuristic=False):
    """Requisiti: PASS/FAIL. Euristiche di diversità: MEASURED con il segnale nella nota."""
    if a.record_by:
        import evidence
        result = "MEASURED" if heuristic else ("PASS" if ok else "FAIL")
        signal = "" if not heuristic else (" — segnale: nessuna convergenza" if ok else " — segnale: CONVERGENZA da rivedere")
        evidence.record_auto(a.apps, check, result, a.record_by, note=note + signal, inputs=compared_files())
        print(f"prova registrata: {check} {result} su {a.apps} (legata a {len(compared_files())} file confrontati)")


def directions():
    return sorted(p.name for p in DIRS.iterdir() if p.is_dir() and re.fullmatch(r"[a-z]", p.name)) if DIRS.exists() else []


def load_apps(path):
    p = ROOT / path
    if not p.exists():
        sys.exit(f"{path} assente: definisci le applicazioni comuni nel brief pack")
    return json.loads(p.read_text(encoding="utf-8"))["apps"]


def cmd_check(a):
    apps = load_apps(a.apps)
    problems = 0
    contract = ROOT / "work/creative-contract.md"
    if not contract.exists():
        print("work/creative-contract.md mancante: lo sprint parte da un contratto creativo")
        problems += 1
    pack = DIRS / "brief-pack.md"
    if not pack.exists() or not re.search(r"^#+\s*Territori esclusi", pack.read_text(encoding="utf-8"), re.M | re.I):
        print("brief-pack.md: manca la sezione 'Territori esclusi' (pre-mortem delle idee ovvie)")
        problems += 1
    for d in directions():
        base = DIRS / d
        md = base / "direction.md"
        if not md.exists():
            print(f"{d}: direction.md mancante")
            problems += 1
        else:
            text = md.read_text(encoding="utf-8")
            for s in SECTIONS:
                if not re.search(rf"^#+\s*{re.escape(s)}", text, re.M | re.I):
                    print(f"{d}: sezione '{s}' mancante in direction.md")
                    problems += 1
            if not re.search(r"\[F-\d{4}\]", text):
                print(f"{d}: direction.md non cita fatti del dossier [F-…]")
                problems += 1
        for app in apps:
            f = base / "apps" / f"{app['id']}.png"
            if not f.exists():
                print(f"{d}: manca {app['id']} ({app['name']})")
                problems += 1
                continue
            size = list(Image.open(f).size)
            if size != list(app["size"]):
                print(f"{d}: {app['id']} è {size[0]}×{size[1]}, richiesto {app['size'][0]}×{app['size'][1]}")
                problems += 1
    n = len(directions())
    ok = not problems and n >= 2
    print(f"{n} direzioni, {len(apps)} applicazioni — " + ("COMPLETO" if ok else f"{problems} problemi"))
    record(a, "board_check", ok, f"{n} direzioni, {problems} problemi")
    sys.exit(0 if ok else 1)


def cmd_boards(a):
    apps = load_apps(a.apps)
    ds = directions()
    labels = [chr(ord("X") + i) if i < 3 else f"V{i}" for i in range(len(ds))]
    rnd = random.Random(a.seed)
    shuffled = ds[:]
    rnd.shuffle(shuffled)
    mapping = dict(zip(labels, shuffled))
    BLIND.parent.mkdir(parents=True, exist_ok=True)
    BLIND.write_text(json.dumps(mapping), encoding="utf-8")
    out = DIRS / "boards"
    out.mkdir(parents=True, exist_ok=True)
    pad, band = 40, 48
    for app in apps:
        w, h = app["size"]
        scale = min(1.0, 900 / max(w, h))
        tw, th = int(w * scale), int(h * scale)
        board = Image.new("RGB", (len(ds) * (tw + pad) + pad, th + 2 * pad + band), (238, 238, 236))
        dr = ImageDraw.Draw(board)
        dr.text((pad, 12), f"{app['id']} — {app['name']} — stesse dimensioni per tutte le direzioni", fill=(30, 30, 30))
        for i, lab in enumerate(labels):
            im = Image.open(DIRS / mapping[lab] / "apps" / f"{app['id']}.png").convert("RGB").resize((tw, th), Image.LANCZOS)
            x = pad + i * (tw + pad)
            board.paste(im, (x, band + pad // 2))
            dr.text((x, band + pad // 2 + th + 8), f"Direzione {lab}", fill=(30, 30, 30))
        board.save(out / f"{app['id']}.png")
        print(f"tavola: {(out / (app['id'] + '.png')).relative_to(ROOT)}")
    print("Etichette anonime X/Y/Z: la mappa è in .agency/blind-map.json; rivelarla solo dopo il primo giudizio.")


def features(img):
    small = img.convert("RGB").resize((96, 96), Image.LANCZOS)
    arr = np.asarray(small).astype(float) / 255
    gray = arr.mean(axis=2)
    px = arr.reshape(-1, 3)
    # Colore medio pesato e dispersione cromatica come firma del linguaggio cromatico.
    return gray, px.mean(0), px.std(0), float((np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean()))


def cmd_diversity(a):
    apps = load_apps(a.apps)
    ds = directions()
    if len(ds) < 2:
        sys.exit("servono almeno due direzioni")
    flags = 0
    print("Confronto a coppie, per applicazione (composizione = SSIM in scala di grigi; colore = distanza RGB media):")
    for i, d1 in enumerate(ds):
        for d2 in ds[i + 1:]:
            ssims, cdist, edist = [], [], []
            for app in apps:
                f1, f2 = DIRS / d1 / "apps" / f"{app['id']}.png", DIRS / d2 / "apps" / f"{app['id']}.png"
                if not (f1.exists() and f2.exists()):
                    continue
                g1, m1, s1, e1 = features(Image.open(f1))
                g2, m2, s2, e2 = features(Image.open(f2))
                ssims.append(structural_similarity(g1, g2, data_range=1.0))
                cdist.append(float(np.linalg.norm(m1 - m2) + np.linalg.norm(s1 - s2)))
                edist.append(abs(e1 - e2))
            if not ssims:
                continue
            ss, cd = float(np.mean(ssims)), float(np.mean(cdist))
            similar = ss > a.max_ssim and cd < a.min_color
            flags += similar
            print(f"  {d1}–{d2}: composizione SSIM {ss:.3f} · colore {cd:.3f} · densità {np.mean(edist):.3f}"
                  + ("  TROPPO SIMILI: non sono direzioni sostanzialmente diverse" if similar else ""))
    print("DIVERSITÀ " + ("SUFFICIENTE" if not flags else f"INSUFFICIENTE ({flags} coppie)"))
    print("Le misure segnalano somiglianze visive grossolane; la differenza di concept la giudica il critico.")
    record(a, "diversity", not flags, f"{flags} coppie troppo simili", heuristic=True)
    sys.exit(1 if flags else 0)


CARD_FIELDS = ["Concept", "Leva di partenza", "Principio compositivo", "Carattere primario", "Colori primari",
               "Linguaggio delle immagini", "Idee ovvie scartate", "Dipendenze di asset"]
# Le scelte di default dei modelli e dei template (vedi references/anti-patterns.md).
DEFAULT_FONTS = {"inter", "poppins", "montserrat", "roboto", "open sans", "lato", "helvetica", "arial",
                 "jetbrains mono", "space grotesk", "dm sans", "manrope", "plus jakarta sans"}
STOP = set("il lo la i gli le un una di da del della dei delle e ed a al alla in nel nella con per tra su che come "
           "è sono non più the of and to a in is".split())


def card(d):
    md = DIRS / d / "direction.md"
    if not md.exists():
        return None
    text = md.read_text(encoding="utf-8")
    fields = {}
    for f in CARD_FIELDS + ["Carattere secondario", "Perché un carattere di default"]:
        m = re.search(rf"^\s*-\s*{re.escape(f)}\s*:\s*(.+)$", text, re.M | re.I)
        if m:
            fields[f] = m.group(1).strip()
    return fields


def font_names(value):
    return {re.split(r"[(,—–-]", v)[0].strip().lower() for v in re.split(r"\s*\+\s*|;", value or "") if v.strip()}


def hexes(value):
    return re.findall(r"#[0-9A-Fa-f]{6}", value or "")


def cmd_lint(a):
    problems = 0
    for d in directions():
        c = card(d)
        if c is None:
            print(f"{d}: direction.md mancante")
            problems += 1
            continue
        for f in CARD_FIELDS:
            if f not in c:
                print(f"{d}: scheda senza '- {f}: …'")
                problems += 1
        fonts = font_names(c.get("Carattere primario")) | font_names(c.get("Carattere secondario"))
        defaults = sorted(fonts & DEFAULT_FONTS)
        if defaults and "Perché un carattere di default" not in c:
            print(f"{d}: carattere di default {', '.join(defaults)} senza '- Perché un carattere di default: …'")
            problems += 1
        if c.get("Carattere primario") and not re.search(r"licen|OFL|EULA", c["Carattere primario"], re.I):
            print(f"{d}: licenza del carattere primario non indicata")
            problems += 1
        if "Colori primari" in c and not hexes(c["Colori primari"]):
            print(f"{d}: colori primari senza valori HEX")
            problems += 1
        if c.get("Idee ovvie scartate") and len([x for x in re.split(r"[;,]", c["Idee ovvie scartate"]) if x.strip()]) < 3:
            print(f"{d}: servono almeno 3 idee ovvie scartate")
            problems += 1
        text = (DIRS / d / "direction.md").read_text(encoding="utf-8")
        m = re.search(r"^#+\s*Decisioni determinanti\s*$(.*?)(?=^#+\s|\Z)", text, re.M | re.S)
        rows = [l for l in (m.group(1).splitlines() if m else []) if l.strip().startswith("|")
                and not re.match(r"^\|\s*-", l.strip()) and "Scelta" not in l and "<" not in l]
        if len(rows) < 3:
            print(f"{d}: 'Decisioni determinanti' con {len(rows)} catene complete (servono ≥ 3: fatto → interpretazione → ipotesi → alternativa → confronto)")
            problems += 1
        else:
            for r in rows:
                cells = [x.strip() for x in r.strip().strip("|").split("|")]
                if len(cells) < 6 or not all(cells[:6]) or not re.search(r"\[F-\d{4}\]", cells[1]):
                    print(f"{d}: catena incompleta o senza fatto citato: {r.strip()[:80]}")
                    problems += 1
        if not re.search(r"Test di sostituzione", text, re.I):
            print(f"{d}: manca il test di sostituzione")
            problems += 1
    ok = not problems
    print("SCHEDE " + ("OK" if ok else f"{problems} problemi"))
    if a.record_by:
        import evidence
        for d in directions():
            md = DIRS / d / "direction.md"
            if md.exists():
                evidence.record_auto(str(md.relative_to(ROOT)), "direction_lint", "PASS" if ok else "FAIL", a.record_by)
        print("prova registrata: direction_lint su ogni direction.md")
    sys.exit(0 if ok else 1)


def oklab(hexv):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hexv[i:i + 2], 16)) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s])


def words(text):
    return {w for w in re.findall(r"[a-zàèéìòóù]{4,}", (text or "").lower()) if w not in STOP}


def cmd_concepts(a):
    ds = directions()
    cards = {d: card(d) or {} for d in ds}
    flags = 0
    for i, d1 in enumerate(ds):
        for d2 in ds[i + 1:]:
            c1, c2 = cards[d1], cards[d2]
            notes = []
            shared_fonts = (font_names(c1.get("Carattere primario")) | font_names(c1.get("Carattere secondario"))) & \
                           (font_names(c2.get("Carattere primario")) | font_names(c2.get("Carattere secondario")))
            if shared_fonts:
                notes.append(f"stessi caratteri: {', '.join(sorted(shared_fonts))}")
            h1, h2 = hexes(c1.get("Colori primari")), hexes(c2.get("Colori primari"))
            if h1 and h2:
                dmin = min(float(np.linalg.norm(oklab(x) - oklab(y))) for x in h1 for y in h2)
                close = sum(1 for x in h1 if min(float(np.linalg.norm(oklab(x) - oklab(y))) for y in h2) < 0.06)
                if close >= max(1, min(len(h1), len(h2)) // 2 + 1):
                    notes.append(f"palette quasi uguale ({close} colori a ΔEok < 0.06)")
            w1 = words(c1.get("Concept")) | words(c1.get("Principio compositivo"))
            w2 = words(c2.get("Concept")) | words(c2.get("Principio compositivo"))
            if w1 and w2:
                jac = len(w1 & w2) / len(w1 | w2)
                if jac > 0.25:
                    notes.append(f"concept e composizione con parole in comune ({jac:.2f}): {', '.join(sorted(w1 & w2)[:6])}")
            if c1.get("Leva di partenza") and c1.get("Leva di partenza", "").lower() == c2.get("Leva di partenza", "").lower():
                notes.append("stessa leva di partenza")
            if c1.get("Linguaggio delle immagini") and words(c1["Linguaggio delle immagini"]) == words(c2.get("Linguaggio delle immagini")):
                notes.append("stesso linguaggio delle immagini")
            same = len(notes) >= 2
            flags += same
            print(f"  {d1}–{d2}: " + ("; ".join(notes) if notes else "differenze sostanziali sui campi misurati")
                  + ("  → NON SOSTANZIALMENTE DIVERSE" if same else ""))
    print("CONCEPT " + ("DIVERSI" if not flags else f"CONVERGENTI ({flags} coppie)"))
    print("Euristica sui campi dichiarati: due idee diverse possono condividere parole o caratteri, e la stessa idea")
    print("può essere descritta con parole diverse. Segnala cosa rivedere; decide il confronto degli artefatti.")
    record(a, "concept_diversity", not flags, f"{flags} coppie convergenti", heuristic=True)
    sys.exit(1 if flags else 0)


def cmd_reveal(_):
    if not BLIND.exists():
        sys.exit("nessuna mappa: esegui prima boards")
    for k, v in json.loads(BLIND.read_text()).items():
        print(f"Direzione {k} = {v.upper()}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["check", "boards", "diversity", "lint", "concepts", "reveal"])
    p.add_argument("--apps", default="work/directions/apps.json")
    p.add_argument("--seed", type=int)
    p.add_argument("--max-ssim", type=float, default=0.75)
    p.add_argument("--min-color", type=float, default=0.12)
    p.add_argument("--record-by", help="registra l'esito in evidence.py come questo agente")
    a = p.parse_args()
    {"check": cmd_check, "boards": cmd_boards, "diversity": cmd_diversity, "lint": cmd_lint,
     "concepts": cmd_concepts, "reveal": cmd_reveal}[a.cmd](a)


if __name__ == "__main__":
    main()
