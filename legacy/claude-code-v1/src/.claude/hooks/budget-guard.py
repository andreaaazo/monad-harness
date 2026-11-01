#!/usr/bin/env python3
"""PreToolUse: tiene il contesto degli agenti entro il budget (design-agency/budgets.json).

Conta per istanza di agente le chiamate web e le immagini lette; blocca le immagini più grandi del
necessario e le riletture dello stesso file immutato; ferma una volta sola a ogni multiplo di
calls_notice, per far decidere all'agente se chiudere. Stato in .claude/runtime/budget/, estensioni
del router in .agency/budget.json. Exit 2 = chiamata bloccata, stderr a Claude.
"""
import fcntl
import json
import os
import re
import struct
import sys
from pathlib import Path

IMAGES = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def image_size(path):
    """Larghezza e altezza da PNG, JPEG o WebP leggendo l'intestazione; None se non si capisce."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                if head[12:16] == b"VP8X":
                    return (int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1)
                return None
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    marker = fh.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        return None
                    length = struct.unpack(">H", fh.read(2))[0]
                    if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                        h, w = struct.unpack(">xHH", fh.read(5))
                        return w, h
                    fh.seek(length - 2, 1)
    except (OSError, struct.error):
        return None
    return None


def block(msg):
    print(f"Bloccato: {msg}", file=sys.stderr)
    sys.exit(2)


try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
try:
    conf = json.loads((root / ".claude/design-agency/budgets.json").read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    sys.exit(0)

agent = event.get("agent_type") or "router"
instance = re.sub(r"[^\w.-]", "_", str(event.get("agent_id") or f"router-{event.get('session_id', 'x')}"))
limits = {**conf["default"], **(conf["router"] if agent == "router" else conf.get("agents", {}).get(agent, {}))}
try:
    extra = json.loads((root / ".agency/budget.json").read_text(encoding="utf-8")).get(agent, {})
except (OSError, json.JSONDecodeError):
    extra = {}
for k, v in extra.items():
    limits[k] = limits.get(k, 0) + v

tool = event.get("tool_name", "")
inp = event.get("tool_input") or {}
state_dir = root / ".claude/runtime/budget"
state_dir.mkdir(parents=True, exist_ok=True)
with open(state_dir / f"{instance}.json", "a+", encoding="utf-8") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
    fh.seek(0)
    raw = fh.read()
    state = json.loads(raw) if raw.strip() else {}
    state.setdefault("agent", agent)
    for k in ("calls", "web", "images"):
        state.setdefault(k, 0)
    state.setdefault("seen", {})
    state.setdefault("messages", {})
    state["calls"] += 1
    verdict = None

    notice = limits.get("calls_notice") or 0
    if notice and state["calls"] % notice == 0:
        verdict = (f"sei a {state['calls']} chiamate ({agent}). Un agente costa di più a ogni passo: se hai ciò che "
                   "serve, consegna ora con ESITO e PROVE. Se devi proseguire, ripeti questa chiamata.")
    elif tool in ("WebSearch", "WebFetch"):
        state["web"] += 1
        if state["web"] > limits["web"]:
            state["web"] -= 1
            verdict = (f"budget web esaurito ({limits['web']} per {agent}). Consegna con ciò che hai trovato, dichiara i "
                       "limiti, e se serve altro chiedilo in RICHIESTE.")
    elif tool == "Read":
        path = Path(str(inp.get("file_path") or ""))
        if path.suffix.lower() in IMAGES and path.exists():
            size = image_size(path)
            side = conf.get("image_max_side", 1600)
            st = path.stat()
            key = f"{path}:{st.st_mtime_ns}:{st.st_size}"
            if size and max(size) > side:
                verdict = (f"{path.name} è {size[0]}×{size[1]}: oltre {side} px arriva ridotta e costa di più. "
                           "Usa render.py (1200 px) per l'insieme e --zoom x,y,w,h per i dettagli.")
            elif state["seen"].get(key, 0) >= conf.get("rereads", 2):
                verdict = f"hai già letto {path.name} {state['seen'][key]} volte e non è cambiato: lavora su ciò che hai visto."
            elif state["images"] >= limits["images"]:
                verdict = (f"budget immagini esaurito ({limits['images']} per {agent}). Guarda fogli di contatto "
                           "(render.py --sheet) e chiedi un'estensione in RICHIESTE se serve.")
            else:
                state["seen"][key] = state["seen"].get(key, 0) + 1
                state["images"] += 1
    elif tool == "SendMessage":
        target = str(inp.get("to") or "?")
        if state["messages"].get(target, 0) >= limits.get("messages", 2):
            verdict = (f"hai già risvegliato {target} {state['messages'][target]} volte. Risvegliare un agente fermo "
                       "riscrive tutto il suo contesto: apri un ticket nuovo con un passaggio breve.")
        else:
            state["messages"][target] = state["messages"].get(target, 0) + 1
    fh.seek(0)
    fh.truncate()
    json.dump(state, fh)
if verdict:
    block(verdict)
sys.exit(0)
