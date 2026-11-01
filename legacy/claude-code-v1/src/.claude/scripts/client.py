#!/usr/bin/env python3
"""Registro del rapporto con il cliente: domande, presentazioni, feedback, approvazioni.

Le parole del cliente si registrano testuali. Un'approvazione è legata all'hash dei file
approvati: se un file cambia dopo l'approvazione, il gate la considera scaduta.

  client.py ask --from <agente> --question "…" --why "perché cambia la soluzione" \
                [--options "A|B|C"] [--blocking] [--ticket T-0003]
  client.py answer Q-0002 --text "risposta testuale del cliente"
  client.py present --round 2 --title "Territori" --files work/direction.md work/proofs/a.png [--questions Q-0004]
  client.py feedback P-0003 --text "feedback testuale del cliente"
  client.py approve --gate direction --files work/direction.md --text "parole del cliente"
  client.py gate direction [--files work/direction.md]     # exit 1 se non approvato o scaduto
  client.py status [--brief]                                # domande aperte, presentazioni in attesa, gate
  client.py ready                                           # fine della fase di ascolto? (comprensione confermata)

Gate standard: understanding, brief, strategy, direction, design, prototype, final (altri nomi ammessi).
Registro: .agency/client.jsonl (solo aggiunte).
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
LOG = ROOT / ".agency/client.jsonl"


def now():
    return datetime.now().isoformat(timespec="seconds")


def rel(p):
    path = (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha(p):
    h = hashlib.sha256()
    with open(ROOT / p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def records():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def append(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def next_id(prefix):
    n = sum(1 for r in records() if r.get("id", "").startswith(prefix + "-"))
    return f"{prefix}-{n + 1:04d}"


def find(rid):
    return next((r for r in records() if r.get("id") == rid), None)


def files_with_hashes(files):
    out = {}
    for f in files:
        r = rel(f)
        if not (ROOT / r).exists():
            sys.exit(f"file inesistente: {f}")
        out[r] = sha(r)
    return out


def state():
    recs = records()
    answered = {r["question"] for r in recs if r["kind"] == "answer"}
    with_feedback = {r["presentation"] for r in recs if r["kind"] == "feedback"}
    questions = [r for r in recs if r["kind"] == "question" and r["id"] not in answered]
    pending = [r for r in recs if r["kind"] == "presentation" and r["id"] not in with_feedback]
    approvals = {}
    for r in recs:
        if r["kind"] == "approval":
            approvals[r["gate"]] = r
    return questions, pending, approvals


def approval_status(appr, files=None):
    """Restituisce (ok, dettagli) per un'approvazione, verificando gli hash."""
    if not appr:
        return False, ["nessuna approvazione registrata"]
    problems = []
    for f, h in appr["files"].items():
        if files and f not in files:
            continue
        if not (ROOT / f).exists():
            problems.append(f"{f}: file non più presente")
        elif sha(f) != h:
            problems.append(f"{f}: modificato dopo l'approvazione del {appr['ts'][:10]}")
    for f in files or []:
        if f not in appr["files"]:
            problems.append(f"{f}: non compreso nell'approvazione")
    return not problems, problems


def cmd_ask(a):
    qid = next_id("Q")
    append({"id": qid, "kind": "question", "ts": now(), "from": a.sender, "question": a.question,
            "why": a.why, "options": a.options.split("|") if a.options else None,
            "blocking": a.blocking, "ticket": a.ticket})
    print(qid)


def cmd_answer(a):
    q = find(a.id)
    if not q or q["kind"] != "question":
        sys.exit(f"domanda inesistente: {a.id}")
    append({"id": next_id("A"), "kind": "answer", "ts": now(), "question": a.id, "text": a.text})
    print(f"{a.id} risposta registrata")


def cmd_present(a):
    pid = next_id("P")
    for q in a.questions or []:
        if not find(q):
            sys.exit(f"domanda inesistente: {q}")
    append({"id": pid, "kind": "presentation", "ts": now(), "round": a.round, "title": a.title,
            "files": files_with_hashes(a.files), "questions": a.questions or []})
    print(pid)


def cmd_feedback(a):
    p = find(a.id)
    if not p or p["kind"] != "presentation":
        sys.exit(f"presentazione inesistente: {a.id}")
    append({"id": next_id("F"), "kind": "feedback", "ts": now(), "presentation": a.id, "text": a.text})
    print(f"feedback su {a.id} registrato: traducilo in work/feedback/round-{p['round']}.md prima di agire")


def cmd_approve(a):
    append({"id": next_id("OK"), "kind": "approval", "ts": now(), "gate": a.gate,
            "files": files_with_hashes(a.files), "text": a.text})
    print(f"gate {a.gate} approvato dal cliente su {len(a.files)} file")


def cmd_gate(a):
    _, _, approvals = state()
    files = [rel(f) for f in a.files] if a.files else None
    ok, problems = approval_status(approvals.get(a.gate), files)
    if ok:
        appr = approvals[a.gate]
        print(f"GATE {a.gate}: APPROVATO dal cliente il {appr['ts'][:10]} — \"{appr['text'][:120]}\"")
        sys.exit(0)
    print(f"GATE {a.gate}: NON APPROVATO")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)


def cmd_status(a):
    questions, pending, approvals = state()
    if a.brief and not (questions or pending or approvals):
        return
    print("Cliente — domande aperte:" if questions else "Cliente — nessuna domanda aperta.")
    for q in questions:
        flag = "BLOCCANTE " if q["blocking"] else ""
        opts = f" [{' | '.join(q['options'])}]" if q["options"] else ""
        print(f"  {q['id']} {flag}({q['from']}) {q['question']}{opts} — perché: {q['why']}")
    for p in pending:
        print(f"  {p['id']} presentazione round {p['round']} \"{p['title']}\" in attesa di feedback")
    for gate, appr in approvals.items():
        ok, problems = approval_status(appr)
        print(f"  gate {gate}: {'approvato' if ok else 'SCADUTO — ' + '; '.join(problems)} ({appr['ts'][:10]})")


def cmd_ready(a):
    """La fase di ascolto finisce quando lo studio ha capito, non dopo N domande."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import facts as facts_mod
    questions, pending, approvals = state()
    problems = []
    blocking = [q for q in questions if q["blocking"]]
    if blocking:
        problems.append(f"{len(blocking)} domande bloccanti senza risposta: " + ", ".join(q["id"] for q in blocking))
    if pending:
        problems.append(f"{len(pending)} presentazioni in attesa di feedback")
    table = facts_mod.facts()
    active = [f for f in table.values() if f["status"] == "active"]
    for topic in facts_mod.REQUIRED_DEFAULT:
        kinds = [f["kind"] for f in active if f["topic"] == topic]
        if not kinds:
            problems.append(f"tema '{topic}' senza fatti")
        elif all(k == "hypothesis" for k in kinds):
            problems.append(f"tema '{topic}' sostenuto solo da ipotesi: verificale con il cliente o dichiaralo")
    ok_u, why_u = approval_status(approvals.get("understanding"))
    if not ok_u:
        problems.append("comprensione non confermata dal cliente (work/context/understanding.md, gate 'understanding'): "
                        + "; ".join(why_u))
    nonblocking = [q for q in questions if not q["blocking"]]
    if problems:
        print("NON ANCORA: lo studio non ha ancora capito abbastanza per passare alla strategia.")
        for x in problems:
            print(f"  - {x}")
        print("Prossimo passo: un altro giro di domande (approfondisci le risposte, chiedi esempi, mostra stimoli), "
              "poi riscrivi understanding.md e chiedi conferma.")
        sys.exit(1)
    print("PRONTO: comprensione confermata dal cliente, temi obbligatori coperti, nessuna domanda bloccante aperta.")
    if nonblocking:
        print(f"  ({len(nonblocking)} domande non bloccanti ancora aperte: portale nel prossimo incontro)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ask")
    s.add_argument("--from", dest="sender", required=True)
    s.add_argument("--question", required=True)
    s.add_argument("--why", required=True, help="perché la risposta cambia la soluzione")
    s.add_argument("--options")
    s.add_argument("--blocking", action="store_true")
    s.add_argument("--ticket")
    s.set_defaults(fn=cmd_ask)
    s = sub.add_parser("answer")
    s.add_argument("id")
    s.add_argument("--text", required=True)
    s.set_defaults(fn=cmd_answer)
    s = sub.add_parser("present")
    s.add_argument("--round", type=int, required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--files", nargs="+", required=True)
    s.add_argument("--questions", nargs="*")
    s.set_defaults(fn=cmd_present)
    s = sub.add_parser("feedback")
    s.add_argument("id")
    s.add_argument("--text", required=True)
    s.set_defaults(fn=cmd_feedback)
    s = sub.add_parser("approve")
    s.add_argument("--gate", required=True)
    s.add_argument("--files", nargs="+", required=True)
    s.add_argument("--text", required=True, help="parole del cliente che approvano")
    s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("gate")
    s.add_argument("gate")
    s.add_argument("--files", nargs="*")
    s.set_defaults(fn=cmd_gate)
    s = sub.add_parser("status")
    s.add_argument("--brief", action="store_true")
    s.set_defaults(fn=cmd_status)
    sub.add_parser("ready", help="lo studio ha capito abbastanza per passare alla strategia?").set_defaults(fn=cmd_ready)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
