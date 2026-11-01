#!/usr/bin/env python3
"""Valutazione creativa ripetibile: lo studio migliora davvero gli output rispetto a un setup essenziale?

  eval_kit.py init  --briefs eval/briefs/*.md --variants full,essential --runs 3 --out eval/run-01
  eval_kit.py collect eval/run-01                     # pacchetto anonimo di immagini + schede di voto
  eval_kit.py score   eval/run-01 ratings/*.csv       # medie e intervalli per variante e criterio

init crea una cartella per brief × variante × ripetizione: "full" copia il template dello studio,
"essential" usa solo .claude/eval/essential-CLAUDE.md (stesso modello, stessi contenuti e asset).
Ogni cartella contiene RUN.md con il comando da eseguire e run.json da compilare (tempo, costo,
interventi umani). Ogni esecuzione scrive in deliverables.txt i file finali da valutare.
collect rende i deliverable in PNG, li rinomina con codici casuali e scrive ratings_template.csv:
i valutatori (designer esperti; per l'usabilità persone del pubblico) non sanno quale variante guardano.
"""
import argparse
import csv
import glob
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[1]
CRITERIA = ["adeguatezza_al_brief", "qualita_compositiva", "tipografia", "specificita", "esperienza_mobile",
            "coerenza_applicazioni", "miglioramento_tra_iterazioni"]


def cmd_init(a):
    out = Path(a.out)
    briefs = [Path(b) for pattern in a.briefs for b in glob.glob(pattern)]
    if not briefs:
        sys.exit("nessun brief trovato")
    for b in briefs:
        for v in a.variants.split(","):
            for r in range(1, a.runs + 1):
                d = out / f"{b.stem}__{v}__r{r}"
                d.mkdir(parents=True, exist_ok=True)
                if v == "full":
                    shutil.copytree(CLAUDE, d / ".claude", dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns("runtime", "__pycache__", "settings.local.json"))
                    if (CLAUDE.parent / ".mcp.json").exists():
                        shutil.copy(CLAUDE.parent / ".mcp.json", d / ".mcp.json")
                else:
                    (d / ".claude").mkdir(exist_ok=True)
                    shutil.copy(CLAUDE / "eval/essential-CLAUDE.md", d / ".claude/CLAUDE.md")
                    if (CLAUDE.parent / ".mcp.json").exists():
                        shutil.copy(CLAUDE.parent / ".mcp.json", d / ".mcp.json")
                (d / "work").mkdir(exist_ok=True)
                shutil.copy(b, d / "work/brief-cliente.md")
                if a.assets:
                    shutil.copytree(a.assets, d / "work/client", dirs_exist_ok=True)
                (d / "RUN.md").write_text(
                    f"# {b.stem} · {v} · ripetizione {r}\n\nStesso modello e budget per tutte le varianti.\n\n"
                    f"```sh\ncd {d}\nclaude --model {a.model}   # poi: lavora sul brief in work/brief-cliente.md\n```\n\n"
                    "Il valutatore umano risponde alle domande dello studio come farebbe il cliente, con le stesse "
                    "risposte preparate per tutte le varianti (work/risposte-cliente.md se presente).\n"
                    "Alla fine: elenca i file finali in deliverables.txt e compila run.json.\n", encoding="utf-8")
                (d / "run.json").write_text(json.dumps({"brief": b.stem, "variant": v, "run": r, "model": a.model,
                                                        "minutes": None, "cost_usd": None, "human_interventions": None,
                                                        "notes": ""}, indent=2), encoding="utf-8")
                print(f"creato {d}")


def cmd_collect(a):
    root = Path(a.run_dir)
    packet = root / "packet"
    packet.mkdir(exist_ok=True)
    rng = random.Random(a.seed)
    mapping, rows = {}, []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and "__" in p.name):
        dl = d / "deliverables.txt"
        if not dl.exists():
            print(f"{d.name}: deliverables.txt mancante, saltato")
            continue
        for line in dl.read_text().splitlines():
            f = (d / line.strip()).resolve()
            if not line.strip() or not f.exists():
                continue
            code = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
            tmp = root / ".render_tmp"
            subprocess.run([str(CLAUDE / "scripts/py"), str(CLAUDE / "scripts/render.py"), str(f), "--out", str(tmp)],
                           capture_output=True, text=True)
            produced = sorted(tmp.rglob("*.png"), key=lambda p: p.stat().st_mtime)
            if not produced:
                print(f"{f}: render non riuscito")
                continue
            for i, img in enumerate(produced):
                name = f"{code}_{i + 1:02d}.png"
                shutil.move(str(img), packet / name)
            shutil.rmtree(tmp, ignore_errors=True)
            brief = d.name.split("__")[0]
            mapping[code] = {"dir": d.name, "file": line.strip()}
            rows.append({"codice": code, "brief": brief, **{c: "" for c in CRITERIA}, "note": ""})
    rng.shuffle(rows)
    (root / ".mapping.json").write_text(json.dumps(mapping, indent=2))
    with open(root / "ratings_template.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["codice", "brief", *CRITERIA, "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} deliverable anonimi in {packet}; scheda: {root / 'ratings_template.csv'} (voti 1–5)")
    print("La mappa codice → variante è in .mapping.json: non darla ai valutatori.")


def cmd_score(a):
    root = Path(a.run_dir)
    mapping = json.loads((root / ".mapping.json").read_text())
    import statistics
    scores = {}
    for f in a.ratings:
        with open(f, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                m = mapping.get(row["codice"])
                if not m:
                    continue
                variant = m["dir"].split("__")[1]
                for c in CRITERIA:
                    if row.get(c, "").strip():
                        scores.setdefault((variant, c), []).append(float(row[c]))
    rng = random.Random(1)
    print(f"{'criterio':30} " + "  ".join(f"{v:>22}" for v in sorted({k[0] for k in scores})))
    for c in CRITERIA:
        cells = []
        for v in sorted({k[0] for k in scores}):
            xs = scores.get((v, c), [])
            if not xs:
                cells.append(f"{'-':>22}")
                continue
            boots = sorted(statistics.mean(rng.choices(xs, k=len(xs))) for _ in range(2000))
            cells.append(f"{statistics.mean(xs):5.2f} [{boots[50]:.2f}–{boots[1949]:.2f}] n={len(xs):<3}")
        print(f"{c:30} " + "  ".join(cells))
    runs = [json.loads(p.read_text()) for p in root.glob("*/run.json")]
    for v in sorted({r["variant"] for r in runs}):
        rs = [r for r in runs if r["variant"] == v]
        num = lambda k: [r[k] for r in rs if isinstance(r.get(k), (int, float))]
        mean = lambda xs: f"{statistics.mean(xs):.1f}" if xs else "-"
        print(f"{v}: minuti {mean(num('minutes'))}, costo $ {mean(num('cost_usd'))}, interventi umani {mean(num('human_interventions'))}")
    print("Intervalli bootstrap al 95%. Differenze dentro gli intervalli non sono miglioramenti dimostrati.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("--briefs", nargs="+", required=True)
    s.add_argument("--variants", default="full,essential")
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--assets", help="cartella di materiali del cliente comune a tutte le esecuzioni")
    s.add_argument("--model", default="claude-opus-5-5")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("collect")
    s.add_argument("run_dir")
    s.add_argument("--seed", type=int, default=7)
    s.set_defaults(fn=cmd_collect)
    s = sub.add_parser("score")
    s.add_argument("run_dir")
    s.add_argument("ratings", nargs="+")
    s.set_defaults(fn=cmd_score)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
