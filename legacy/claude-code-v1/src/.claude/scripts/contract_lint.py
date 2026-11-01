#!/usr/bin/env python3
"""Controlla il contratto creativo e i documenti di direzione: sezioni presenti e compilate,
aggettivi di valore non tradotti in effetti e mezzi osservabili.

  python3 .claude/scripts/contract_lint.py [work/creative-contract.md] [altri .md …] [--record-by agente]

Un aggettivo come "premium", "moderno", "elegante", "impeccabile" è ammesso solo se la stessa frase
dice come si vede (con quali immagini, caratteri, ritmi, materiali, movimenti). Il controllo è
un'euristica sul testo: segnala dove manca la traduzione in forma, non giudica la qualità.
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(Path(__file__).resolve().parent))
SECTIONS = ["Percezione da produrre", "Cosa del cliente deve emergere", "Decisione visiva caratterizzante",
            "Dove sperimentare", "Cosa deve restare familiare e immediato", "Come giudicheremo il risultato"]
VAGUE = ["premium", "moderno", "moderna", "moderni", "pulito", "pulita", "elegante", "eleganti", "minimal",
         "minimale", "innovativo", "innovativa", "audace", "impeccabile", "raffinato", "raffinata", "di lusso",
         "lussuoso", "d'impatto", "accattivante", "fresco", "fresca", "dinamico", "dinamica", "world class",
         "di primo livello", "awwwards", "wow", "iconico", "iconica", "senza tempo", "bello", "bella"]
# Parole che indicano un mezzo osservabile nella stessa frase.
MEANS = r"(fotograf|immagin|caratter|tipograf|corpo|peso|interlinea|griglia|margin|colonn|ritmo|scala|contrast|" \
        r"colore|palette|materia|carta|superfic|movimento|transizion|durata|curva|spazio|bianco|gerarchi|" \
        r"composizion|ritagli|inquadratur|luce|texture|segno|lettering|sequenza|montaggio|pagin|frame|interazion|" \
        r"\d+\s?(px|mm|pt|ms|%))"


def check_file(path, require_sections):
    text = path.read_text(encoding="utf-8")
    problems = []
    if require_sections:
        for s in SECTIONS:
            m = re.search(rf"^#+\s*{re.escape(s)}\s*$(.*?)(?=^#+\s|\Z)", text, re.M | re.S)
            body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip() if m else ""
            if not m:
                problems.append(f"sezione mancante: {s}")
            elif len(body) < 40 or body.startswith(("Cosa deve", "Il contenuto, la", "La scelta che", "Le parti", "Gli artefatti")):
                problems.append(f"sezione non compilata: {s}")
        if not re.search(r"\[F-\d{4}\]", text):
            problems.append("nessun fatto del dossier citato [F-…]")
    clean = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for sentence in re.split(r"(?<=[.!?;])\s+|\n", clean):
        low = sentence.lower()
        hits = [w for w in VAGUE if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low)]
        if hits and not re.search(MEANS, low) and not re.search(r"niente|non [\w ]*\"|vietat|evitare|\"", low):
            problems.append(f"aggettivo senza forma osservabile ({', '.join(hits)}): «{sentence.strip()[:110]}»")
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="*")
    p.add_argument("--record-by")
    a = p.parse_args()
    files = a.files or ["work/creative-contract.md"]
    total = 0
    for f in files:
        path = Path(f) if Path(f).exists() else ROOT / f
        if not path.exists():
            print(f"{f}: inesistente (modello: .claude/design-agency/templates/creative-contract.md)")
            total += 1
            continue
        probs = check_file(path, require_sections=path.name == "creative-contract.md")
        total += len(probs)
        print(f"{f}: " + ("ok" if not probs else f"{len(probs)} problemi"))
        for x in probs:
            print(f"  - {x}")
        if a.record_by:
            import evidence
            evidence.record_auto(str(path), "contract_check", "FAIL" if probs else "PASS", a.record_by,
                                 note="euristica sul testo: sezioni e aggettivi tradotti in forma")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
