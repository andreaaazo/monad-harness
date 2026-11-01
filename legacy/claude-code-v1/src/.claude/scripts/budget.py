#!/usr/bin/env python3
"""Budget di contesto degli agenti.

  budget.py status
  budget.py extend <agente> web|images|calls_notice <quantità> --by router --why "…"

I limiti stanno in design-agency/budgets.json; hooks/budget-guard.py li applica. Solo il router
estende, con un motivo: le estensioni restano in .agency/budget.json e nella storia del progetto.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
FILE = ROOT / ".agency/budget.json"
STATE = ROOT / ".claude/runtime/budget"
LOG = ROOT / ".agency/decisions.md"


def cmd_status(_):
    rows = {}
    for p in sorted(STATE.glob("*.json")) if STATE.exists() else []:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        r = rows.setdefault(s.get("agent", "?"), [0, 0, 0, 0])
        r[0] += 1
        r[1] += s.get("calls", 0)
        r[2] += s.get("web", 0)
        r[3] += s.get("images", 0)
    print(f"{'agente':22}{'istanze':>8}{'chiamate':>10}{'web':>6}{'immagini':>10}")
    for agent, (n, calls, web, images) in sorted(rows.items(), key=lambda x: -x[1][1]):
        print(f"{agent:22}{n:>8}{calls:>10}{web:>6}{images:>10}")


def cmd_extend(a):
    if a.by != "router":
        sys.exit("solo il router estende un budget")
    if len(a.why.strip()) < 15:
        sys.exit("--why: scrivi perché serve l'estensione")
    data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    agent = data.setdefault(a.agent, {})
    agent[a.what] = agent.get(a.what, 0) + a.amount
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"\n- {datetime.now():%Y-%m-%d %H:%M} budget {a.agent} {a.what} +{a.amount}: {a.why.strip()}\n")
    print(f"{a.agent}: {a.what} +{a.amount}")


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("status").set_defaults(fn=cmd_status)
e = sub.add_parser("extend")
e.add_argument("agent")
e.add_argument("what", choices=["web", "images", "calls_notice"])
e.add_argument("amount", type=int)
e.add_argument("--by", required=True)
e.add_argument("--why", required=True)
e.set_defaults(fn=cmd_extend)
a = p.parse_args()
a.fn(a)
