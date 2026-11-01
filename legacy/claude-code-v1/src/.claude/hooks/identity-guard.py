#!/usr/bin/env python3
"""PreToolUse: la firma nei registri è quella di chi sta davvero lavorando.

Confronta --by, --record-by e --from dei comandi dello studio con l'identità reale del chiamante
(agent_type dell'hook; assente = router). Blocca le firme non letterali, le scritture dirette sui
registri e, per i subagenti, i comandi riservati al router. Exit 2 = chiamata bloccata.
Limite dichiarato: legge il testo del comando, quindi un comando lanciato da uno script di shell
scritto apposta non viene visto; le scritture dirette sui registri restano bloccate solo se
visibili nel comando.
"""
import json
import re
import shlex
import sys

REGISTRIES = (".agency/evidence.jsonl", ".agency/renders.jsonl", ".agency/client.jsonl", ".agency/derivations.jsonl",
              ".agency/facts.jsonl", ".agency/budget.json", ".agency/tickets/")
CLIENT_WRITES = ("ask", "answer", "present", "feedback", "approve")


def block(msg):
    print(f"Bloccato: {msg}", file=sys.stderr)
    sys.exit(2)


try:
    event = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

tool = event.get("tool_name", "")
inp = event.get("tool_input") or {}
me = event.get("agent_type") or event.get("agent_name") or "router"

if tool in ("Write", "Edit", "NotebookEdit"):
    path = str(inp.get("file_path") or inp.get("notebook_path") or "")
    if any(r in path for r in REGISTRIES):
        block(f"{path} è un registro dello studio: si scrive solo con gli script (ticket.py, evidence.py, client.py).")
    sys.exit(0)

if tool != "Bash":
    sys.exit(0)
cmd = str(inp.get("command") or "")

# Scritture sui registri dalla shell: redirezioni e comandi che modificano un file.
for r in REGISTRIES:
    if r not in cmd:
        continue
    pat = re.escape(r)
    if re.search(rf">>?\s*['\"]?\S*{pat}", cmd) or re.search(rf"\b(tee|sed\s+-i|rm|mv|cp|truncate|dd)\b[^|;&]*{pat}", cmd) \
            or re.search(rf"(open|write_text|write_bytes)\([^)]*{pat}", cmd):
        block(f"{r} si scrive solo con gli script dello studio, non dalla shell.")

if not re.search(r"\.claude/(scripts|skills)/", cmd):
    sys.exit(0)

for flag, raw in re.findall(r"(?:^|\s)(--by|--record-by|--from)(?:\s+|=)(\"[^\"]*\"|'[^']*'|\S+)", cmd):
    if flag == "--from" and not re.search(r"ticket\.py\s+new", cmd):
        continue
    if re.search(r"[$`]", raw):
        block(f"{flag} deve essere il tuo nome scritto per esteso, non una variabile ({raw}).")
    try:
        value = shlex.split(raw)[0]
    except (ValueError, IndexError):
        block(f"{flag}: valore non leggibile ({raw}).")
    if value != me:
        block(f"{flag} {value}: stai lavorando come {me}. Firma con il tuo nome: i registri dicono chi ha fatto cosa.")

lock = re.search(r"craft_lock\.py\s+acquire\s+\S+\s+(\S+)", cmd)
if lock and lock.group(1).strip("'\"") != me:
    block(f"il lock va preso a nome tuo ({me}), non di {lock.group(1)}.")

if me != "router":
    write = re.search(r"client\.py\s+(\w+)", cmd)
    if write and write.group(1) in CLIENT_WRITES:
        block("solo il router parla con il cliente: metti la domanda o la presentazione in DOMANDE CLIENTE.")
    if re.search(r"budget\.py\s+extend", cmd):
        block("il budget lo estende il router: chiedilo in RICHIESTE, con il motivo.")
sys.exit(0)
