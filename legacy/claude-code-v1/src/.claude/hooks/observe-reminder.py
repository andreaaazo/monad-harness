#!/usr/bin/env python3
"""PostToolUse: dopo aver scritto un file visivo, ricorda di renderizzarlo e guardarlo.

Non blocca nulla: aggiunge al contesto dell'agente il comando di render. La regola dura sta
in evidence.py (una revisione visiva vale solo con un render della versione attuale).
"""
import json
import sys
from pathlib import Path

VISUAL = {".svg", ".html", ".htm", ".css", ".pdf", ".json", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)
inp = event.get("tool_input") or {}
path = str(inp.get("file_path") or "")
ext = Path(path).suffix.lower()
if not path or ext not in VISUAL or "/.agency/" in path or path.endswith(("package.json", "tokens.json")):
    sys.exit(0)
target = path if ext != ".css" else "la pagina HTML che usa questo CSS"
msg = (f"Hai modificato {path}. Prima di dichiararlo fatto: "
       f".claude/scripts/py .claude/scripts/render.py {target} — poi apri le immagini prodotte con Read "
       f"e guardale alla dimensione d'uso. Ciò che non hai visto è NOT_VERIFIED.")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
sys.exit(0)
