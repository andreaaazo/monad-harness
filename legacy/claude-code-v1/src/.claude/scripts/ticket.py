#!/usr/bin/env python3
"""Ticket tra reparti: contratto di passaggio con stato del lavoro e verdetto separati.

Stato del lavoro (`status`), una sola risposta alla domanda "a che punto è":
  open → delivered → accepted       consegnato dal destinatario, accettato dal mittente
             ↘ rework → delivered   rimandato dal mittente con il motivo
  blocked (--resume lo riapre) · cancelled
Verdetto (`verdict`), solo per ticket qa e revisione: READY | REVISE | NOT_VERIFIED. Dice cosa ha
trovato il revisore, non a che punto è il ticket: una revisione che boccia è un lavoro consegnato.

Alla consegna si controlla sempre tutto: ogni output esiste; ogni output ha almeno un controllo o
un'esenzione motivata; gli input non sono cambiati; le prove sono fresche; per le produzioni con un
mezzo, il master si apre e le consegne ne derivano (master.py). I controlli indipendenti (registro
design-agency/checks.json) si verificano all'accettazione, perché li firma un altro.

  ticket.py new --from <mittente> --to <agente> --type produzione|consulenza|revisione|ricerca|qa|consegna|disaccordo \
        --title "…" --request "…" | --request-file f.md   --inputs <file…>   --outputs <file o glob…> \
        --accept <check> | '<pattern>=<check>+<check>' … | none   [--exempt '<file o glob>=motivo'] \
        [--medium vettoriale|motion|immagine|interfaccia|3d|nessuno …] [--medium-why "…"] [--no-master '<glob>=motivo'] \
        [--criteria "R1…"] [--parent T-0001] [--qa L1..L4] [--after-gate <gate…>]
  ticket.py deliver T-0004 --by <destinatario> --note "…" [--verdict READY|REVISE|NOT_VERIFIED] \
        [--outputs <altri file>] [--exempt '<file>=motivo'] [--input-change "perché non invalida il lavoro"]
  ticket.py accept  T-0004 --by <mittente> [--note "…"]
  ticket.py rework  T-0004 --by <mittente> --reason "…"
  ticket.py block   T-0004 --by <agente> --reason "…"     |  ticket.py resume T-0004 --by <agente> --reason "…"
  ticket.py cancel  T-0004 --by <mittente> --reason "…"
  ticket.py verify T-0004          # controlla senza cambiare stato
  ticket.py show T-0004 | list [--open] [--to agente] | tree | lineage <file>

Controlli: nomi del registro, oppure req:<nome> per un requisito del progetto.
Registro: .agency/tickets/T-NNNN.json (dati) e T-NNNN.md (lettura).
"""
import argparse
import fnmatch
import glob
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
DIR = ROOT / ".agency/tickets"
TYPES = ("produzione", "consulenza", "revisione", "ricerca", "qa", "consegna", "disaccordo")
STATES = ("open", "delivered", "accepted", "rework", "blocked", "cancelled")
ACTIVE = ("open", "delivered", "rework", "blocked")
VERDICTS = ("READY", "REVISE", "NOT_VERIFIED")
NO_ACCEPT_TYPES = ("consulenza", "ricerca", "disaccordo")
REVIEW_TYPES = ("qa", "revisione")
GLOB_CHARS = "*?["
sys.path.insert(0, str(Path(__file__).resolve().parent))


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def rel(p):
    if any(c in str(p) for c in GLOB_CHARS):
        return os.path.relpath(p, ROOT) if os.path.isabs(p) else str(p)
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
    with open(ROOT / p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(tid):
    p = DIR / f"{tid}.json"
    if not p.exists():
        sys.exit(f"ticket inesistente: {tid}")
    return json.loads(p.read_text(encoding="utf-8"))


def all_tickets():
    if not DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR.glob("T-*.json")) if p.stat().st_size]


def save(t):
    for path, text in ((DIR / f"{t['id']}.json", json.dumps(t, ensure_ascii=False, indent=2)), (DIR / f"{t['id']}.md", render_md(t))):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)


def render_md(t):
    state = t["status"] + (f" · verdetto {t['verdict']}" if t.get("verdict") else "")
    lines = [f"# {t['id']} — {t['title']}", "",
             f"- from: {t['from']}", f"- to: {t['to']}", f"- type: {t['type']}", f"- status: {state}",
             f"- parent: {t['parent'] or '-'}", f"- qa: {t['qa']}", f"- after_gate: {','.join(t['after_gate']) or '-'}",
             f"- medium: {', '.join(t.get('medium') or []) or '-'}", f"- created: {t['created']}", "", "## Richiesta", "",
             t["request"], "", "## Input (versione all'apertura)", ""]
    lines += [f"- `{f}` sha256:{h[:12]}" for f, h in t["inputs"].items()] or ["- nessuno"]
    lines += ["", "## Output attesi", ""] + ([f"- `{o}`" for o in t["outputs"]] or ["- nessuno"])
    lines += ["", "## Accettazione", "", f"- controlli: {', '.join(t['accept']) or 'nessuno'}"]
    lines += [f"- esente `{k}`: {v}" for k, v in (t.get("exempt") or {}).items()]
    lines += [f"- senza master `{k}`: {v}" for k, v in (t.get("no_master") or {}).items()]
    if t.get("criteria"):
        lines += ["", t["criteria"]]
    lines += ["", "## Storia", ""]
    lines += [f"- {h['ts']} {h['event']} ({h['by']}): {h['note']}" for h in t["history"]]
    if t.get("delivered"):
        lines += ["", "## Versioni consegnate", ""] + [f"- `{f}` sha256:{h[:12]}" for f, h in t["delivered"].items()]
    return "\n".join(lines) + "\n"


def next_id():
    DIR.mkdir(parents=True, exist_ok=True)
    n = max([int(t["id"][2:]) for t in all_tickets()] or [0]) + 1
    while True:
        tid = f"T-{n:04d}"
        try:
            os.close(os.open(DIR / f"{tid}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
            return tid
        except FileExistsError:
            n += 1


def stale_inputs(t):
    out = []
    for f, h in t["inputs"].items():
        if not (ROOT / f).exists():
            out.append(f"{f}: non esiste più")
        elif sha(f) != h:
            out.append(f"{f}: cambiato dopo l'apertura del ticket")
    return out


def matches(f, pattern):
    return fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(Path(f).name, pattern)


def key_value(items, flag):
    out = {}
    for item in items or []:
        key, sep, why = item.partition("=")
        if not sep or len(why.strip()) < 10:
            sys.exit(f"{flag} '{item}': scrivi '<file o glob>=motivo', con un motivo vero")
        out[rel(key.strip())] = why.strip()
    return out


def parse_accept(specs):
    """Accetta 'check' oppure 'pattern=check+check'; restituisce le specifiche pulite o esce."""
    import evidence
    accept = [c.strip() for spec in specs for c in spec.split(",") if c.strip()]
    for spec in accept:
        names = (spec.split("=", 1)[1] if "=" in spec else spec).split("+")
        for name in (n for n in names if n):
            why = evidence.check_problem(name)
            if why:
                sys.exit(f"--accept: {why}")
    return accept


def expected(t):
    """Output reali: i glob si espandono; un glob senza file è un problema, non un elenco vuoto."""
    files, empty = [], []
    for o in t["outputs"]:
        if any(c in o for c in GLOB_CHARS):
            found = sorted(rel(x) for x in glob.glob(str(ROOT / o), recursive=True) if Path(x).is_file())
            files += found
            if not found:
                empty.append(o)
        else:
            files.append(o)
    return list(dict.fromkeys(files)), empty


def checks_for(t, f):
    """'check' vale per tutti gli output, 'pattern=check+check' per i file che corrispondono."""
    out = []
    for spec in t["accept"]:
        if "=" in spec:
            pattern, checks = spec.split("=", 1)
            if matches(f, pattern):
                out += [c for c in checks.split("+") if c]
        else:
            out += [c for c in spec.split("+") if c]
    return list(dict.fromkeys(out))


def exempted(t, f):
    return any(f == k or matches(f, k) for k in t.get("exempt") or {})


def coverage_problems(t, files):
    if t["type"] in NO_ACCEPT_TYPES:
        return []
    out = []
    for f in files:
        if t["type"] in REVIEW_TYPES and f.endswith(".md"):
            continue  # il referto del revisore: le prove stanno sui file revisionati
        if not checks_for(t, f) and not exempted(t, f):
            out.append(f"{f}: nessun controllo di accettazione lo copre (aggiungilo o --exempt '<file>=motivo')")
    return out


def evidence_problems(t, files, independent):
    """independent=False alla consegna (prove dell'autore), True all'accettazione (tutte)."""
    import evidence
    table = evidence.latest()
    review = t["type"] in REVIEW_TYPES
    probs = []
    for f in files:
        for check in checks_for(t, f):
            if review and t.get("verdict_pending") == "NOT_VERIFIED":
                continue
            is_independent = evidence.is_independent(check)
            if is_independent and not independent and not review:
                continue
            e = table.get((f, check))
            if not e:
                probs.append(f"{f}: manca la prova '{check}'")
                continue
            who = evidence.signer(e)
            if review and who != t["to"]:
                probs.append(f"{f}: '{check}' è firmata da {who}, serve {t['to']} (la verifica la esegue il revisore)")
                continue
            if is_independent and not review and who == t["to"]:
                probs.append(f"{f}: '{check}' è firmata dall'autore {who}: serve un revisore indipendente")
                continue
            if evidence.freshness(e) != "fresh":
                probs.append(f"{f}: '{check}' è {evidence.freshness(e)} (file cambiato dopo la prova)")
                continue
            if review and t.get("verdict_pending") == "REVISE":
                continue  # il revisore boccia: la prova esiste, l'esito può essere FAIL
            if e["result"] not in evidence.accepted(check):
                probs.append(f"{f}: '{check}' è {e['result']}")
    return probs


def master_problems(t, files):
    media = [m for m in t.get("medium") or [] if m != "nessuno"]
    if not media:
        return []
    import master
    probs = []
    masters = []
    for m in media:
        ext = master.MEDIA[m]["master"]
        found = [f for f in files if f.lower().endswith(ext)]
        if not found:
            probs.append(f"mezzo {m}: manca il master {ext} ({master.MEDIA[m]['tool']}) tra gli output")
        masters += found
    for f in masters:
        why = master.problem(f)
        if why:
            probs.append(f"{f}: {why}")
    exts = tuple(x for m in media for x in master.MEDIA[m]["exports"])
    derived = [m for m in masters if not m.lower().endswith(".blend")]
    for f in files:
        if not f.lower().endswith(exts) or f.startswith("work/proofs/") or "/proofs/" in f:
            continue
        if f in masters or any(f == k or matches(f, k) for k in t.get("no_master") or {}):
            continue
        if derived and (ROOT / f).exists():
            why = master.derived_problem(f, derived)
            if why:
                probs.append(f"{f}: {why}")
    return probs


def delivery_problems(t, input_change=None):
    files, empty = expected(t)
    problems = [f"{g}: nessun file corrisponde" for g in empty]
    problems += [f"{o}: output mancante" for o in files if not (ROOT / o).exists()]
    problems += [f"{o}: è una cartella, dichiara i file o un glob" for o in files if (ROOT / o).is_dir()]
    if not input_change:
        problems += [f"input superato — {s}" for s in stale_inputs(t)]
    present = [o for o in files if (ROOT / o).is_file()]
    problems += coverage_problems(t, present)
    problems += evidence_problems(t, present, independent=False)
    problems += master_problems(t, present)
    return present, problems


def event(t, name, by, note):
    t["history"].append({"ts": now(), "event": name, "by": by, "note": note or ""})


def require(t, by, who, action, states):
    if by != t[who]:
        sys.exit(f"{t['id']}: {action} spetta a {t[who]} ({'mittente' if who == 'from' else 'destinatario'}), non a {by}")
    if t["status"] not in states:
        sys.exit(f"{t['id']}: {action} non è ammesso dallo stato {t['status']}")


def cmd_new(a):
    if a.parent and not (DIR / f"{a.parent}.json").exists():
        sys.exit(f"ticket padre inesistente: {a.parent}")
    request = Path(a.request_file).read_text(encoding="utf-8") if a.request_file else a.request
    if not request:
        sys.exit("servono --request o --request-file")
    accept = [] if a.accept == ["none"] else parse_accept(a.accept)
    if not accept and a.type not in NO_ACCEPT_TYPES:
        sys.exit(f"--accept none è ammesso solo per {', '.join(NO_ACCEPT_TYPES)}: indica i controlli di accettazione")
    if not a.outputs and a.type not in ("disaccordo",):
        sys.exit("--outputs: dichiara i file che il destinatario deve produrre (anche un report .md)")
    outputs = [rel(o) for o in a.outputs or []]
    for o, raw in zip(outputs, a.outputs or []):
        if raw.endswith("/") or (ROOT / o).is_dir():
            sys.exit(f"--outputs: {raw} è una cartella. Dichiara i file o un glob (work/x/*.png): "
                     "i controlli si applicano ai file, una cartella passerebbe senza verifiche")
    media = a.medium or []
    if a.type == "produzione" and not media:
        sys.exit("--medium: dichiara il mezzo (vettoriale, motion, immagine, interfaccia, 3d) o 'nessuno' con --medium-why")
    if "nessuno" in media and not (a.medium_why and len(a.medium_why.strip()) >= 10):
        sys.exit("--medium nessuno richiede --medium-why: perché questo lavoro non ha un master Craft (es. solo testo)")
    exempt = key_value(a.exempt, "--exempt")
    probe = {"accept": accept, "exempt": exempt, "type": a.type, "outputs": outputs}
    for spec in accept:
        if "=" in spec:
            pattern = spec.split("=", 1)[0]
            if not any(matches(o, pattern) or fnmatch.fnmatch(pattern, o) for o in outputs):
                sys.exit(f"--accept: il pattern '{pattern}' non corrisponde a nessun output dichiarato: "
                         "non controllerebbe nulla")
    for o in outputs:
        if a.type in NO_ACCEPT_TYPES or (a.type in REVIEW_TYPES and o.endswith(".md")):
            continue
        if not checks_for(probe, o) and not exempted(probe, o) and not any(fnmatch.fnmatch(p, o) for p in pattern_list(accept)):
            sys.exit(f"output senza controllo: {o}. Aggiungi un controllo in --accept o --exempt '{o}=motivo'")
    inputs = {}
    for f in a.inputs or []:
        r = rel(f)
        if not (ROOT / r).exists():
            sys.exit(f"input inesistente: {f}")
        inputs[r] = sha(r)
    visual_ext = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf", ".figcraft", ".vectorcraft", ".pcraft", ".ecproj")
    if a.type == "produzione" and set(a.after_gate or []) & {"direction", "design", "prototype"} \
            and not any(f.lower().endswith(visual_ext) for f in inputs):
        sys.exit("ticket rifiutato: una produzione dopo la scelta della direzione porta riferimenti visivi negli --inputs "
                 "(esempi approvati, immagini annotate, dettagli da preservare), non solo testo")
    for gate in a.after_gate or []:
        import client
        _, _, approvals = client.state()
        ok, problems = client.approval_status(approvals.get(gate))
        if not ok:
            sys.exit(f"ticket rifiutato: il gate '{gate}' non è approvato dal cliente ({'; '.join(problems)}). "
                     f"Presenta il lavoro e registra l'approvazione con client.py approve.")
    tid = next_id()
    t = {"id": tid, "title": a.title, "from": a.sender, "to": a.to, "type": a.type, "status": "open", "verdict": None,
         "parent": a.parent, "qa": a.qa, "after_gate": a.after_gate or [], "created": now(),
         "request": request.strip(), "criteria": a.criteria, "inputs": inputs, "outputs": outputs, "accept": accept,
         "exempt": exempt, "medium": media, "medium_why": a.medium_why, "no_master": key_value(a.no_master, "--no-master"),
         "history": [], "delivered": {}}
    event(t, "open", a.sender, a.title)
    save(t)
    print(tid)


def pattern_list(accept):
    return [s.split("=", 1)[0] for s in accept if "=" in s]


def cmd_deliver(a):
    t = load(a.id)
    require(t, a.by, "to", "la consegna", ("open", "rework"))
    review = t["type"] in REVIEW_TYPES
    if review and not a.verdict:
        sys.exit(f"{a.id}: un ticket {t['type']} si consegna con --verdict READY|REVISE|NOT_VERIFIED")
    if a.verdict and not review:
        sys.exit(f"{a.id}: --verdict vale solo per ticket qa e revisione")
    if a.verdict == "NOT_VERIFIED" and not a.note:
        sys.exit("--verdict NOT_VERIFIED richiede --note: cosa non è stato possibile verificare e perché")
    t["outputs"] = list(dict.fromkeys(t["outputs"] + [rel(o) for o in a.outputs or []]))
    t["exempt"] = {**(t.get("exempt") or {}), **key_value(a.exempt, "--exempt")}
    t["verdict_pending"] = a.verdict
    present, problems = delivery_problems(t, a.input_change)
    if problems:
        print(f"{a.id}: consegna rifiutata")
        for p in problems:
            print(f"  {p}")
        print("Correggi, oppure: ticket.py block <id> --by <agente> --reason \"…\"")
        sys.exit(1)
    t["delivered"] = {o: sha(o) for o in present}
    t["status"] = "delivered"
    t["verdict"] = a.verdict
    t.pop("verdict_pending", None)
    note = (a.note or "") + (f" [input cambiati accettati: {a.input_change}]" if a.input_change else "")
    event(t, "delivered", a.by, note)
    save(t)
    print(f"{a.id} delivered" + (f" · verdetto {a.verdict}" if a.verdict else ""))


def cmd_accept(a):
    t = load(a.id)
    require(t, a.by, "from", "l'accettazione", ("delivered",))
    t["verdict_pending"] = t.get("verdict")
    problems = [f"{f}: modificato dopo la consegna" for f, h in t["delivered"].items()
                if not (ROOT / f).exists() or sha(f) != h]
    problems += evidence_problems(t, list(t["delivered"]), independent=True)
    t.pop("verdict_pending", None)
    if problems:
        print(f"{a.id}: accettazione rifiutata")
        for p in problems:
            print(f"  {p}")
        print("Procura le prove mancanti (ticket di revisione), oppure: ticket.py rework <id> --by <mittente> --reason \"…\"")
        sys.exit(1)
    t["status"] = "accepted"
    event(t, "accepted", a.by, a.note)
    save(t)
    print(f"{a.id} accepted")


def cmd_rework(a):
    t = load(a.id)
    require(t, a.by, "from", "il rinvio", ("delivered", "accepted"))
    t["status"], t["verdict"] = "rework", None
    event(t, "rework", a.by, a.reason)
    save(t)
    print(f"{a.id} rework")


def cmd_block(a):
    t = load(a.id)
    if a.by not in (t["from"], t["to"]):
        sys.exit(f"{a.id}: il blocco spetta a {t['to']} o {t['from']}, non a {a.by}")
    if t["status"] not in ("open", "rework"):
        sys.exit(f"{a.id}: il blocco non è ammesso dallo stato {t['status']}")
    t["status"] = "blocked"
    event(t, "blocked", a.by, a.reason)
    save(t)
    print(f"{a.id} blocked")


def cmd_resume(a):
    t = load(a.id)
    if a.by not in (t["from"], t["to"]):
        sys.exit(f"{a.id}: la ripresa spetta a {t['to']} o {t['from']}, non a {a.by}")
    if t["status"] != "blocked":
        sys.exit(f"{a.id}: non è bloccato ({t['status']})")
    t["status"] = "open"
    event(t, "resumed", a.by, a.reason)
    save(t)
    print(f"{a.id} open")


def cmd_cancel(a):
    t = load(a.id)
    require(t, a.by, "from", "l'annullamento", ACTIVE)
    t["status"] = "cancelled"
    event(t, "cancelled", a.by, a.reason)
    save(t)
    print(f"{a.id} cancelled")


def cmd_verify(a):
    t = load(a.id)
    t["verdict_pending"] = t.get("verdict")
    _, issues = delivery_problems(t)
    issues += [f"{p}" for p in evidence_problems(t, [o for o in expected(t)[0] if (ROOT / o).is_file()], independent=True)
               if p not in issues]
    for d, h in t.get("delivered", {}).items():
        if (ROOT / d).exists() and sha(d) != h:
            issues.append(f"{d}: modificato dopo la consegna del ticket")
    print(f"{a.id} [{t['status']}] " + ("ok" if not issues else f"{len(issues)} problemi"))
    for i in issues:
        print(f"  {i}")
    sys.exit(1 if issues else 0)


def cmd_show(a):
    print(render_md(load(a.id)))


def cmd_list(a):
    for t in all_tickets():
        if a.open and t["status"] not in ACTIVE:
            continue
        if a.to and t["to"] != a.to:
            continue
        verdict = f" · {t['verdict']}" if t.get("verdict") else ""
        print(f"{t['id']}  {t['status']:9}{verdict} {t['from']} → {t['to']}  [{t['type']}]  {t['title']}")


def cmd_tree(_):
    children = {}
    for t in all_tickets():
        children.setdefault(t["parent"], []).append(t)

    def show(parent, depth):
        for t in children.get(parent, []):
            print("  " * depth + f"{t['id']} {t['to']} [{t['status']}] {t['title']}")
            show(t["id"], depth + 1)
    show(None, 0)


def cmd_lineage(a):
    f = rel(a.file)
    current = sha(f) if (ROOT / f).exists() else None
    for t in all_tickets():
        if f in t["inputs"]:
            mark = "versione attuale" if t["inputs"][f] == current else "versione precedente"
            print(f"usato da   {t['id']} ({t['to']}, {t['status']}) — {mark}")
        if f in t.get("delivered", {}):
            mark = "versione attuale" if t["delivered"][f] == current else "poi modificato"
            print(f"prodotto da {t['id']} ({t['to']}, {t['status']}) — {mark}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--from", dest="sender", required=True)
    n.add_argument("--to", required=True)
    n.add_argument("--type", choices=TYPES, required=True)
    n.add_argument("--title", required=True)
    n.add_argument("--request")
    n.add_argument("--request-file")
    n.add_argument("--inputs", nargs="*")
    n.add_argument("--outputs", nargs="*")
    n.add_argument("--accept", nargs="+", required=True,
                   help="controlli richiesti: 'check' per tutti gli output o 'pattern=check+check' (es. '*.png=visual_review'); 'none'")
    n.add_argument("--exempt", nargs="*", help="'<file o glob>=motivo': output senza controlli, con il motivo")
    n.add_argument("--medium", nargs="+", choices=["vettoriale", "motion", "immagine", "interfaccia", "3d", "nessuno"])
    n.add_argument("--medium-why")
    n.add_argument("--no-master", nargs="*", help="'<glob>=motivo': output che legittimamente non derivano dal master")
    n.add_argument("--criteria")
    n.add_argument("--parent")
    n.add_argument("--qa", default="L2", choices=["L1", "L2", "L3", "L4"])
    n.add_argument("--after-gate", nargs="*")
    n.set_defaults(fn=cmd_new)
    d = sub.add_parser("deliver")
    d.add_argument("id")
    d.add_argument("--by", required=True)
    d.add_argument("--note")
    d.add_argument("--verdict", choices=VERDICTS)
    d.add_argument("--outputs", nargs="*")
    d.add_argument("--exempt", nargs="*")
    d.add_argument("--input-change")
    d.set_defaults(fn=cmd_deliver)
    c = sub.add_parser("accept")
    c.add_argument("id")
    c.add_argument("--by", required=True)
    c.add_argument("--note")
    c.set_defaults(fn=cmd_accept)
    for name, fn in (("rework", cmd_rework), ("block", cmd_block), ("resume", cmd_resume), ("cancel", cmd_cancel)):
        s = sub.add_parser(name)
        s.add_argument("id")
        s.add_argument("--by", required=True)
        s.add_argument("--reason", required=True)
        s.set_defaults(fn=fn)
    for name, fn in (("verify", cmd_verify), ("show", cmd_show)):
        s = sub.add_parser(name)
        s.add_argument("id")
        s.set_defaults(fn=fn)
    ls = sub.add_parser("list")
    ls.add_argument("--open", action="store_true")
    ls.add_argument("--to")
    ls.set_defaults(fn=cmd_list)
    sub.add_parser("tree").set_defaults(fn=cmd_tree)
    li = sub.add_parser("lineage")
    li.add_argument("file")
    li.set_defaults(fn=cmd_lineage)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
