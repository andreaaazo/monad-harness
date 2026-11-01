#!/usr/bin/env python3
"""Crea le cartelle di lavoro del progetto, solo dentro la radice (alcuni strumenti, come FigCraft,
non creano le cartelle quando salvano).

  python3 .claude/scripts/workdir.py                       # struttura standard
  python3 .claude/scripts/workdir.py work/design work/proofs/web
"""
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2]).resolve()
STANDARD = [".agency", "work/client", "work/context", "work/design", "work/source", "work/exports",
            "work/proofs", "work/research", "work/references", "work/copy", "work/feedback", "work/directions"]

args = sys.argv[1:]
if any(a in ("-h", "--help") for a in args):
    print(__doc__)
    sys.exit(0)
bad = [a for a in args if a.startswith("-")]
if bad:
    sys.exit(f"rifiutato: {', '.join(bad)} non è una cartella. Uso: workdir.py [cartella…]")
targets = args or STANDARD
for t in targets:
    p = (ROOT / t).resolve()
    if p != ROOT and ROOT not in p.parents:
        sys.exit(f"rifiutato: {t} è fuori dalla radice del progetto")
    p.mkdir(parents=True, exist_ok=True)
    print(f"ok {p.relative_to(ROOT)}")
