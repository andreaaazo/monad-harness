#!/usr/bin/env python3
"""Stato della toolchain dello studio rispetto a .claude/tools/registry.json.

  .claude/scripts/py .claude/scripts/tools.py check [--tier core|extra|all] [--json]
  .claude/scripts/py .claude/scripts/tools.py plan          # cosa installare e come

Esce con 1 se manca un tool core. Va eseguito con .claude/scripts/py (venv dello studio).
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".claude/tools/registry.json"
HOME_DIR = Path(os.environ.get("DESIGN_AGENCY_HOME", Path.home() / ".local/share/design-agency"))


def present(tool):
    kind, name = tool["kind"], tool["name"]
    if kind == "exe":
        return shutil.which(name) is not None
    if kind == "python":
        return importlib.util.find_spec(name) is not None
    if kind == "node":
        return (HOME_DIR / "node/node_modules" / name / "package.json").exists()
    raise ValueError(f"kind sconosciuto: {kind}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["check", "plan"])
    p.add_argument("--tier", choices=["core", "extra", "all"], default="all")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    tools = json.loads(REGISTRY.read_text(encoding="utf-8"))["tools"]
    rows = [dict(t, present=present(t)) for t in tools if args.tier in ("all", t["tier"])]
    in_venv = sys.prefix != sys.base_prefix
    missing_core = [r for r in rows if r["tier"] == "core" and not r["present"]]

    if args.cmd == "plan":
        need_setup = any(r["install"].startswith("setup_tools") and not r["present"] for r in rows)
        apt = sorted({r["install"].split("apt: ", 1)[1] for r in rows
                      if not r["present"] and r["install"].startswith("apt: ")})
        if need_setup:
            print("Toolchain utente (senza sudo):  bash .claude/tools/setup_tools.sh")
        if apt:
            print("Tool di sistema (esegue l'utente):  sudo apt install " + " ".join(apt))
        other = [r for r in rows if not r["present"] and not r["install"].startswith(("apt: ", "setup_tools"))]
        for r in other:
            print(f"{r['name']}: {r['install']}")
        if not (need_setup or apt or other):
            print("Niente da installare.")
        return

    if args.json:
        print(json.dumps({"python": sys.executable, "venv": in_venv, "tools": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"python: {sys.executable}" + ("" if in_venv else "  (sistema: eseguire con .claude/scripts/py)"))
        for r in rows:
            mark = "ok " if r["present"] else ("MISS" if r["tier"] == "core" else "--  ")
            print(f"  {mark} {r['tier']:5} {r['kind']:6} {r['name']:22} {r['for']}")
        print(f"{sum(r['present'] for r in rows)}/{len(rows)} presenti; core mancanti: {len(missing_core)}")
    sys.exit(1 if missing_core else 0)


if __name__ == "__main__":
    main()
