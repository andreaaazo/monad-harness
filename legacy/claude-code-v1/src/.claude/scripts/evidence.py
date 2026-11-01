#!/usr/bin/env python3
"""Registro delle prove: ogni verifica è legata all'hash del file controllato.

Se il file cambia dopo la verifica, la prova diventa STALE e non vale più come PASS.
I nomi dei controlli stanno in design-agency/checks.json (req:<nome> per i requisiti del progetto).
I controlli indipendenti non li firma l'autore del file, ricavato dai ticket di produzione; un
FAIL resta valido sulla stessa versione finché non lo cambia chi l'ha firmato o il file cambia.

  evidence.py record --file work/exports/logo.svg --check svg_audit --result PASS \
                     --by qa-inspector [--proof work/proofs/logo_proof.png] [--ticket T-0004] [--note "…"]
  evidence.py observe FILE --by <agente> --seen "cosa ho visto nel render"   # render + visual_review in un passo
  evidence.py judge FILE --compare <riferimento|alternativa|versione precedente…> --why "…" --by <agente> --result PASS|FAIL
                                           # qualità percettiva: solo con confronto visivo, firmata da un revisore
                                           # (anche --check stress_test|critique|charter_review|distinctiveness)
  evidence.py status [FILE ...]            # ultimo esito per file e controllo, con freschezza
  evidence.py gate FILE ... --require svg_audit,logo_proof,critique
                                           # exit 1 se un controllo richiesto manca, non è PASS o è STALE

Registro: .agency/evidence.jsonl (una riga JSON per prova, solo aggiunte).
"""
import argparse
import fnmatch
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
LOG = ROOT / ".agency/evidence.jsonl"
RESULTS = ("PASS", "FAIL", "MEASURED", "NOT_VERIFIED", "NOT_APPLICABLE")
# Tre tipi di prova, da non confondere:
#   misura eseguita  → MEASURED (lo script ha misurato; non dice che il risultato sia buono)
#   requisito        → PASS / FAIL (una soglia tecnica o normativa è soddisfatta o no)
#   giudizio         → PASS / FAIL con prova osservata e motivazione (OBSERVED)
CLAUDE_DIR = Path(__file__).resolve().parents[1]
CHECKS = json.loads((CLAUDE_DIR / "design-agency/checks.json").read_text(encoding="utf-8"))["checks"]
MEASUREMENTS = {n for n, c in CHECKS.items() if c["kind"] == "measure"}
JUDGEMENTS = sorted(n for n, c in CHECKS.items() if c["kind"] == "judgement")
RENDERS = ROOT / ".agency/renders.jsonl"
TICKETS = ROOT / ".agency/tickets"
# Controlli che richiedono di aver guardato il risultato: la prova deve essere un render
# della versione attuale del file, prodotto da render.py (o dagli script di prova indicati).
OBSERVED = {n for n, c in CHECKS.items() if c["kind"] == "observation" or c.get("observed")}


def roles():
    return {p.stem for p in (CLAUDE_DIR / "agents").glob("*.md")} | {"router"}


def check_problem(name):
    if name.startswith("req:") and len(name) > 4:
        return None
    if name in CHECKS:
        return None
    return f"controllo sconosciuto '{name}': usa un nome di design-agency/checks.json o req:<nome> per un requisito del progetto"


def is_independent(name):
    return bool(CHECKS.get(name, {}).get("independent"))


def accepted(name):
    return ("PASS", "NOT_APPLICABLE", "MEASURED") if name in MEASUREMENTS else ("PASS", "NOT_APPLICABLE")


def signer(e):
    return str(e.get("by") or "").removesuffix(" (auto)")


def authors(file_rel):
    """Chi ha prodotto il file: i destinatari dei ticket di produzione che lo dichiarano in output."""
    out = set()
    if not TICKETS.exists():
        return out
    for p in TICKETS.glob("T-*.json"):
        if not p.stat().st_size:
            continue
        t = json.loads(p.read_text(encoding="utf-8"))
        if t.get("type") != "produzione":
            continue
        declared = list(t.get("outputs") or []) + list(t.get("delivered") or {})
        if any(file_rel == o or fnmatch.fnmatch(file_rel, o) for o in declared):
            out.add(t.get("to"))
    return out


def identity_guard(file_rel, check, by):
    """Controlla nome del controllo, firmatario e indipendenza prima di ogni registrazione."""
    who = str(by).removesuffix(" (auto)")
    why = check_problem(check)
    if why:
        sys.exit(why)
    if who not in roles():
        sys.exit(f"--by '{who}': non è un ruolo dello studio (agenti in .claude/agents, oppure router)")
    spec = CHECKS.get(check) or {}
    if spec.get("independent"):
        if who in authors(file_rel):
            sys.exit(f"'{check}' è indipendente: {who} è l'autore di {file_rel} e non può firmarlo")
        if spec.get("roles") and who not in spec["roles"]:
            sys.exit(f"'{check}' lo firma {', '.join(spec['roles'])}, non {who}")


def rendered_from(file_rel, file_sha, proof_rel):
    if not RENDERS.exists():
        return False
    for line in RENDERS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("source") == file_rel and e.get("source_sha") == file_sha and proof_rel in e.get("proofs", []):
            return True
    return False


def rel(p):
    # Percorsi relativi: alla cartella corrente se il file esiste lì, altrimenti alla radice del progetto.
    path = Path(p)
    if not path.is_absolute():
        path = path if path.exists() else ROOT / path
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha(p):
    h = hashlib.sha256()
    with open(ROOT / p if not Path(p).is_absolute() else p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entries():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def latest(files=None):
    """Esito valido per file e controllo. L'ultima voce vale, ma sulla stessa versione del file un
    FAIL non si copre con il PASS di qualcun altro: resta finché lo cambia il firmatario o cambia il file."""
    last = {}
    for e in entries():
        if files and e["file"] not in files:
            continue
        key = (e["file"], e["check"])
        versions = last.setdefault(key, [e["sha256"], {}])
        if versions[0] != e["sha256"]:
            last[key] = versions = [e["sha256"], {}]
        versions[1].pop(signer(e), None)
        versions[1][signer(e)] = e
    table = {}
    for key, (_, by_signer) in last.items():
        ordered = list(by_signer.values())
        table[key] = next((e for e in reversed(ordered) if e["result"] == "FAIL"), ordered[-1])
    return table


def freshness(e):
    """Fresca se il file e tutti gli input confrontati sono ancora alla versione registrata."""
    try:
        if sha(e["file"]) != e["sha256"]:
            return "STALE"
        for f, h in (e.get("inputs") or {}).items():
            if not (ROOT / f).exists() or sha(f) != h:
                return "STALE"
        return "fresh"
    except OSError:
        return "MISSING"


def record_auto(file, check, result, by, proof=None, note=None, ticket=None, inputs=None):
    """Registrazione da parte di uno script: l'esito è quello calcolato, non dichiarato.
    `inputs`: altri file confrontati; se uno cambia, la prova scade."""
    f = rel(file)
    identity_guard(f, check, by)
    ins = {rel(x): sha(rel(x)) for x in (inputs or []) if (ROOT / rel(x)).exists()}
    e = {"ts": datetime.now().isoformat(timespec="seconds"), "file": f, "sha256": sha(f), "check": check,
         "result": result, "by": f"{by} (auto)", "proof": rel(proof) if proof else None, "ticket": ticket,
         "note": note, "inputs": ins or None}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def cmd_record(a):
    if not Path(ROOT / rel(a.file)).exists():
        sys.exit(f"file inesistente: {a.file}")
    if a.proof and not Path(ROOT / rel(a.proof)).exists():
        sys.exit(f"prova inesistente: {a.proof}")
    if a.result == "NOT_APPLICABLE" and not a.note:
        sys.exit("NOT_APPLICABLE richiede --note con la motivazione")
    f = rel(a.file)
    identity_guard(f, a.check, a.by)
    if CHECKS.get(a.check, {}).get("kind") == "judgement" and a.result == "PASS":
        sys.exit(f"'{a.check}' è un giudizio: si registra con evidence.py judge, con un confronto visivo")
    if a.check in OBSERVED and a.result == "PASS":
        if not a.proof:
            sys.exit(f"'{a.check}' richiede --proof: un render della versione attuale (render.py)")
        if not rendered_from(f, sha(f), rel(a.proof)):
            sys.exit(f"'{a.check}': {a.proof} non risulta un render della versione attuale di {f}. "
                     f"Esegui .claude/scripts/py .claude/scripts/render.py {f}, guarda le immagini, poi registra.")
    e = {"ts": datetime.now().isoformat(timespec="seconds"), "file": f, "sha256": sha(f), "check": a.check,
         "result": a.result, "by": a.by, "proof": rel(a.proof) if a.proof else None,
         "ticket": a.ticket, "note": a.note}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"registrato: {f} · {a.check} · {a.result}")


def cmd_observe(a):
    """Rende il file se non c'è un render della versione attuale, poi registra visual_review
    con la descrizione di ciò che è stato visto. Senza descrizione concreta non registra nulla.
    Limite dichiarato: dimostra che un render della versione attuale esiste e che l'osservatore
    ne ha scritto una descrizione; non dimostra la qualità dell'attenzione."""
    import subprocess
    f = rel(a.file)
    if not (ROOT / f).exists():
        sys.exit(f"file inesistente: {a.file}")
    identity_guard(f, "visual_review", a.by)
    if len(a.seen.strip()) < 40:
        sys.exit("--seen: descrivi cosa hai visto nel render (almeno una frase concreta: composizione, "
                 "testo, bordi, colori, difetti). Una revisione senza osservazione non si registra.")
    current = sha(f)
    proof = None
    if RENDERS.exists():
        for line in reversed(RENDERS.read_text(encoding="utf-8").splitlines()):
            e = json.loads(line) if line.strip() else {}
            if e.get("source") == f and e.get("source_sha") == current and e.get("proofs"):
                proof = e["proofs"][0]
                break
    if proof is None:
        here = Path(__file__).resolve().parent
        r = subprocess.run([str(here / "py"), str(here / "render.py"), f, "--out", a.out],
                           capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT)))
        print(r.stdout.strip())
        print(f"Render creato ora: aprilo con Read e guardalo, poi ripeti observe con ciò che hai visto.")
        sys.exit(1)
    e = {"ts": datetime.now().isoformat(timespec="seconds"), "file": f, "sha256": current, "check": "visual_review",
         "result": a.result, "by": a.by, "proof": proof, "ticket": a.ticket, "note": f"visto: {a.seen.strip()}"}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"registrato: {f} · visual_review · {a.result} (prova {proof})")


def cmd_judge(a):
    """Giudizio di qualità percettiva: vale solo con un confronto visivo esplicito.
    Il file giudicato deve avere un render della versione attuale; i termini di confronto
    (riferimento di livello, alternativa, versione precedente) devono esistere."""
    f = rel(a.file)
    identity_guard(f, a.check, a.by)
    current = sha(f)
    proof = None
    if RENDERS.exists():
        for line in reversed(RENDERS.read_text(encoding="utf-8").splitlines()):
            e = json.loads(line) if line.strip() else {}
            if e.get("source") == f and e.get("source_sha") == current and e.get("proofs"):
                proof = e["proofs"][0]
                break
    if proof is None:
        sys.exit(f"{f}: nessun render della versione attuale (render.py), il giudizio non ha una prova")
    missing = [c for c in a.compare if not (ROOT / rel(c)).exists()]
    if missing:
        sys.exit(f"termini di confronto inesistenti: {', '.join(missing)}")
    if len(a.why.strip()) < 60:
        sys.exit("--why: motiva il giudizio con elementi visibili del confronto (cosa raggiunge il livello, cosa resta indietro)")
    e = {"ts": datetime.now().isoformat(timespec="seconds"), "file": f, "sha256": current, "check": a.check,
         "result": a.result, "by": a.by, "proof": proof, "ticket": a.ticket,
         "note": f"confronto con {', '.join(rel(c) for c in a.compare)}: {a.why.strip()}",
         "inputs": {rel(c): sha(rel(c)) for c in a.compare}}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"registrato: {f} · {a.check} · {a.result} (giudizio con confronto: {len(a.compare)} termini)")


def cmd_status(a):
    files = {rel(f) for f in a.files} if a.files else None
    for (f, check), e in sorted(latest(files).items()):
        print(f"{e['result']:14} {freshness(e):7} {check:18} {f}  ({e['by']}, {e['ts']})")


def cmd_gate(a):
    required = [c.strip() for c in a.require.split(",") if c.strip()]
    table = latest()
    failures = 0
    for f in (rel(x) for x in a.files):
        for check in required:
            e = table.get((f, check))
            if not e:
                print(f"MANCA       {check:18} {f}")
                failures += 1
                continue
            fr = freshness(e)
            ok = e["result"] in accepted(check) and fr == "fresh"
            failures += not ok
            print(f"{'ok' if ok else 'BLOCCA':11} {check:18} {f}  {e['result']} {fr}")
    print("GATE " + ("SUPERATO" if not failures else f"NON SUPERATO ({failures})"))
    sys.exit(1 if failures else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--file", required=True)
    r.add_argument("--check", required=True)
    r.add_argument("--result", required=True, choices=RESULTS)
    r.add_argument("--by", required=True)
    r.add_argument("--proof")
    r.add_argument("--ticket")
    r.add_argument("--note")
    r.set_defaults(fn=cmd_record)
    o = sub.add_parser("observe", help="render (se serve) + revisione visiva con descrizione di ciò che si è visto")
    o.add_argument("file")
    o.add_argument("--by", required=True)
    o.add_argument("--seen", required=True, help="cosa hai visto nel render")
    o.add_argument("--result", default="PASS", choices=["PASS", "FAIL"])
    o.add_argument("--ticket")
    o.add_argument("--out", default="work/proofs/render")
    o.set_defaults(fn=cmd_observe)
    j = sub.add_parser("judge", help="giudizio di qualità percettiva con confronto visivo obbligatorio")
    j.add_argument("file")
    j.add_argument("--compare", nargs="+", required=True, help="riferimento di livello, alternativa o versione precedente")
    j.add_argument("--why", required=True)
    j.add_argument("--by", required=True)
    j.add_argument("--check", default="quality_judgement", choices=JUDGEMENTS)
    j.add_argument("--result", required=True, choices=["PASS", "FAIL"])
    j.add_argument("--ticket")
    j.set_defaults(fn=cmd_judge)
    s = sub.add_parser("status")
    s.add_argument("files", nargs="*")
    s.set_defaults(fn=cmd_status)
    g = sub.add_parser("gate")
    g.add_argument("files", nargs="+")
    g.add_argument("--require", required=True)
    g.set_defaults(fn=cmd_gate)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
