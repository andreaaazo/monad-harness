#!/usr/bin/env python3
"""PreToolUse: blocca le chiamate MCP VectorCraft/EffectCraft/FigCraft/PhotoCraft senza un lock di scrittura valido.

Se l'input dell'hook indica l'agente chiamante (agent_type) e il lock appartiene a un
altro agente, blocca anche quella chiamata. Exit 2 = chiamata bloccata, stderr a Claude.
"""
import json
import os
import sys
import time
from pathlib import Path

try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

tool = event.get("tool_name", "")
server = next((s for s in ("vectorcraft", "effectcraft", "figcraft", "photocraft") if tool.startswith(f"mcp__{s}__")), None)
if server is None:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
lock_file = root / ".claude/runtime/locks" / f"{server}.json"
hint = (f"python3 .claude/scripts/craft_lock.py acquire {server} <tuo-nome-agente> <documento> --ticket <T-id>")
try:
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print(f"Bloccato: nessun lock di scrittura su {server}. Un solo autore per server Craft. "
          f"Acquisisci il lock prima di usare i tool: {hint}", file=sys.stderr)
    sys.exit(2)

if lock.get("expires_at", 0) <= time.time():
    print(f"Bloccato: il lock su {server} di {lock.get('holder')} è scaduto. "
          f"Verifica lo stato del documento, poi riacquisisci: {hint}", file=sys.stderr)
    sys.exit(2)

caller = event.get("agent_type") or event.get("agent_name")
if caller and lock.get("holder") not in (caller, "router"):
    print(f"Bloccato: {server} è assegnato a {lock.get('holder')} (documento {lock.get('document')}). "
          f"Tu sei {caller}: chiedi al router di riassegnare il server.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
