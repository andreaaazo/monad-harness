#!/usr/bin/env python3
"""PreToolUse: isola gli esploratori dello sprint delle direzioni (direction-a, -b, -c, …).

Un esploratore legge solo il brief pack e i materiali comuni, e scrive solo nella propria
cartella work/directions/<lettera>/. Non può leggere o elencare le cartelle delle altre
direzioni, né le tavole di confronto o la selezione, finché lo sprint è in corso.
L'input dell'hook contiene agent_type per le chiamate dei subagenti (verificato).
"""
import json
import re
import sys

try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

agent = event.get("agent_type") or ""
m = re.fullmatch(r"direction-([a-z])", agent)
if not m:
    sys.exit(0)
own = m.group(1)
tool = event.get("tool_name", "")
inp = event.get("tool_input") or {}
text = " ".join(str(v) for v in inp.values()) if isinstance(inp, dict) else str(inp)

# Riferimenti ad altre direzioni o ai materiali di confronto e selezione.
foreign = [d for d in re.findall(r"work/directions/([a-z])(?:/|\b)", text) if d != own]
forbidden = re.search(r"work/directions/(boards|selection|blind)", text)
wildcard = re.search(r"work/directions/(\*|\?|\[|\{)", text) or re.search(r"work/directions/?(\s|$|\"|')", text)
if foreign or forbidden or (wildcard and tool in ("Glob", "Grep", "Bash", "LS")):
    print(f"Bloccato: sei {agent}. Durante l'esplorazione lavori senza vedere le altre direzioni "
          f"(né tavole o selezione). Usa solo il brief pack e la tua cartella work/directions/{own}/.",
          file=sys.stderr)
    sys.exit(2)

if tool in ("Write", "Edit", "NotebookEdit"):
    path = str(inp.get("file_path") or inp.get("notebook_path") or "")
    if f"work/directions/{own}/" not in path:
        print(f"Bloccato: {agent} scrive solo in work/directions/{own}/ (tentato: {path}).", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
