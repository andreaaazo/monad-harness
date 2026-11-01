#!/usr/bin/env python3
"""Dossier del progetto: ogni fatto con la sua provenienza.

  confermato dal cliente  --kind client     --ref A-0003|F-0002|OK-0001   (id reale di client.py)
  emerge da una fonte     --kind source     --ref <URL o file>  --date AAAA-MM-GG
  ipotesi dello studio    --kind hypothesis --why "ragionamento" --test "come la verifichiamo"

  facts.py add --topic audience --kind client --text "…" --ref A-0003 [--by brand-strategist]
  facts.py confirm F-0007 --ref A-0009          # un'ipotesi confermata dal cliente
  facts.py reject  F-0007 --ref A-0009|<fonte>  # smentita: non si usa più
  facts.py list [--topic t] [--kind k]
  facts.py coverage [--require audience,objective,…]   # exit 1 se un tema obbligatorio manca
  facts.py check work/strategy.md               # citazioni [F-0001]: inesistenti, smentite, ipotesi
  facts.py export                                # scrive work/context/dossier.md (generato)

Registro: .agency/facts.jsonl (solo aggiunte).
"""
import argparse
import json
sys_path_added = False
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
LOG = ROOT / ".agency/facts.jsonl"
sys.path.insert(0, str(Path(__file__).resolve().parent))
CLIENT_LOG = ROOT / ".agency/client.jsonl"
TOPICS = {
    "objective": "Obiettivo e criteri di successo del cliente",
    "audience": "Pubblico: chi sceglie, chi usa, cosa sa, cosa deve pensare e fare",
    "context": "Contesto d'uso: dove, quando, su quali supporti, a che distanza, in che situazione",
    "competitors": "Concorrenti e convenzioni di categoria",
    "content": "Contenuti reali: testi, dati, nomi, prodotti, servizi",
    "constraints": "Vincoli produttivi, tecnici, legali, di budget e di tempo",
    "success": "Come si misura il successo del lavoro",
    "product": "Prodotto o servizio: come funziona, cosa lo distingue",
    "materials": "Materiali, superfici, processi, finiture del mondo del cliente",
    "language": "Linguaggio del cliente e del pubblico: parole, tono, lingue",
    "documents": "Documenti esistenti del cliente",
    "photos": "Fotografie e immagini disponibili",
    "users": "Utenti reali e loro situazioni",
    "situations": "Situazioni d'uso concrete del brand e dei suoi artefatti",
    "brand": "Identità esistente ed equity",
    "timeline": "Tempi e tappe",
}
REQUIRED_DEFAULT = ["objective", "audience", "context", "competitors", "content", "constraints", "success"]
CITE = re.compile(r"\[(F-\d{4})\]")


def now():
    return datetime.now().isoformat(timespec="seconds")


def records():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def append(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def client_ids():
    if not CLIENT_LOG.exists():
        return {}
    out = {}
    for line in CLIENT_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["kind"] in ("answer", "feedback", "approval"):
                out[r["id"]] = r
    return out


def facts():
    """Stato corrente di ogni fatto, applicando conferme e smentite."""
    table = {}
    for r in records():
        if r["op"] == "add":
            table[r["id"]] = dict(r, status="active")
        elif r["op"] in ("confirm", "reject") and r["fact"] in table:
            f = table[r["fact"]]
            if r["op"] == "confirm":
                f.update(kind="client", ref=r["ref"], status="active", confirmed=r["ts"])
            else:
                f.update(status="rejected", rejected_by=r["ref"], rejected=r["ts"])
    return table


def validate_ref(kind, ref, a):
    if kind == "client":
        ids = client_ids()
        if ref not in ids:
            sys.exit(f"--ref {ref}: non è una risposta, un feedback o un'approvazione registrati in client.py. "
                     f"Un fatto 'client' deve risalire a parole del cliente.")
    elif kind == "source":
        if not ref:
            sys.exit("--kind source richiede --ref (URL o file)")
        if ref.startswith(("http://", "https://")):
            if not a.date:
                sys.exit("una fonte web richiede --date (data di consultazione)")
        elif not (ROOT / ref).exists():
            sys.exit(f"--ref {ref}: file inesistente")
    elif kind == "hypothesis":
        if not (a.why and a.test):
            sys.exit("un'ipotesi richiede --why (ragionamento) e --test (come verificarla)")


def cmd_add(a):
    if a.topic not in TOPICS:
        sys.exit(f"tema sconosciuto: {a.topic}. Temi: {', '.join(TOPICS)}")
    validate_ref(a.kind, a.ref, a)
    fid = f"F-{len([r for r in records() if r['op'] == 'add']) + 1:04d}"
    append({"op": "add", "id": fid, "ts": now(), "topic": a.topic, "kind": a.kind, "text": a.text,
            "ref": a.ref, "date": a.date, "why": a.why, "test": a.test, "by": a.by})
    print(fid)


def cmd_confirm(a, op):
    if a.fact not in facts():
        sys.exit(f"fatto inesistente: {a.fact}")
    if op == "confirm" or a.ref.startswith(("A-", "F-", "OK-")):
        if a.ref not in client_ids():
            sys.exit(f"--ref {a.ref}: non registrato in client.py")
    append({"op": op, "fact": a.fact, "ref": a.ref, "ts": now()})
    print(f"{a.fact} {'confermato dal cliente' if op == 'confirm' else 'smentito'} ({a.ref})")


def label(kind):
    return {"client": "CLIENTE", "source": "FONTE", "hypothesis": "IPOTESI"}[kind]


def cmd_list(a):
    for f in facts().values():
        if a.topic and f["topic"] != a.topic or a.kind and f["kind"] != a.kind:
            continue
        status = "" if f["status"] == "active" else " [SMENTITO]"
        ref = f["ref"] or f"perché: {f['why']}"
        print(f"{f['id']} {label(f['kind']):8} {f['topic']:12} {f['text']}  ({ref}){status}")


def cmd_coverage(a):
    required = a.require.split(",") if a.require else REQUIRED_DEFAULT
    by_topic = {}
    for f in facts().values():
        if f["status"] == "active":
            by_topic.setdefault(f["topic"], []).append(f["kind"])
    missing = 0
    for t in TOPICS:
        kinds = by_topic.get(t, [])
        mix = ", ".join(f"{label(k)} {kinds.count(k)}" for k in ("client", "source", "hypothesis") if kinds.count(k))
        req = t in required
        if req and not kinds:
            state = "MANCA"
            missing += 1
        elif kinds and all(k == "hypothesis" for k in kinds):
            state = "solo ipotesi"
        else:
            state = "ok" if kinds else "-"
        if req or kinds:
            print(f"{state:13} {'*' if req else ' '} {t:12} {mix}")
    print("COPERTURA " + ("COMPLETA" if not missing else f"INCOMPLETA ({missing} temi obbligatori senza fatti)"))
    print("(* = obbligatorio; 'solo ipotesi' va dichiarato al cliente o verificato prima di decidere)")
    if a.record_by:
        cmd_export(a)
        import evidence
        evidence.record_auto("work/context/dossier.md", "dossier_coverage", "FAIL" if missing else "PASS", a.record_by,
                             note=f"{missing} temi obbligatori mancanti", inputs=[".agency/facts.jsonl"])
        print("prova registrata: dossier_coverage su work/context/dossier.md")
    sys.exit(1 if missing else 0)


def cmd_check(a):
    path = Path(a.file)
    if not path.is_absolute() and not path.exists():
        path = ROOT / path
    text = path.read_text(encoding="utf-8")
    table = facts()
    cited = list(dict.fromkeys(CITE.findall(text)))
    errors = 0
    for fid in cited:
        f = table.get(fid)
        if not f:
            print(f"ERRORE {fid}: citato ma inesistente")
            errors += 1
        elif f["status"] == "rejected":
            print(f"ERRORE {fid}: smentito ({f.get('rejected_by')}) ma ancora usato — {f['text']}")
            errors += 1
        elif f["kind"] == "hypothesis":
            print(f"IPOTESI {fid}: {f['text']} — dichiararla come ipotesi nel testo")
    kinds = [table[c]["kind"] for c in cited if c in table]
    print(f"{a.file}: {len(cited)} fatti citati (cliente {kinds.count('client')}, fonte {kinds.count('source')}, "
          f"ipotesi {kinds.count('hypothesis')})" + ("" if cited else " — nessuna citazione: le affermazioni non sono tracciate"))
    if a.record_by:
        import evidence
        evidence.record_auto(a.file, "facts_check", "FAIL" if errors or not cited else "PASS", a.record_by,
                             note=f"{len(cited)} citati, ipotesi {kinds.count('hypothesis')}, errori {errors}. "
                                  "Verifica riferimenti e stati dei fatti, non che la fonte sostenga ogni affermazione.",
                             inputs=[".agency/facts.jsonl", ".agency/client.jsonl"])
        print(f"prova registrata: facts_check su {a.file}")
    sys.exit(1 if errors or not cited else 0)


def cmd_export(a):
    table = facts()
    out = ROOT / "work/context/dossier.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Dossier del progetto", "", f"Generato da `facts.py export` il {date.today()}. Non modificare a mano: "
             "aggiungi fatti con `facts.py add`.", "",
             "Legenda: **CLIENTE** = confermato dal cliente · **FONTE** = emerge da una fonte · "
             "**IPOTESI** = ipotesi dello studio da verificare.", ""]
    for t, desc in TOPICS.items():
        items = [f for f in table.values() if f["topic"] == t]
        if not items:
            continue
        lines += [f"## {desc}", ""]
        for kind in ("client", "source", "hypothesis"):
            for f in (x for x in items if x["kind"] == kind):
                ref = f["ref"] if kind != "hypothesis" else f"perché: {f['why']} · verifica: {f['test']}"
                strike = "~~" if f["status"] == "rejected" else ""
                note = f" — smentito da {f.get('rejected_by')}" if f["status"] == "rejected" else ""
                lines.append(f"- {strike}**{label(kind)}** [{f['id']}] {f['text']}{strike} ({ref}{', ' + f['date'] if f.get('date') else ''}){note}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"scritto: {out.relative_to(ROOT)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--topic", required=True)
    s.add_argument("--kind", required=True, choices=["client", "source", "hypothesis"])
    s.add_argument("--text", required=True)
    s.add_argument("--ref")
    s.add_argument("--date")
    s.add_argument("--why")
    s.add_argument("--test")
    s.add_argument("--by", default="router")
    s.set_defaults(fn=cmd_add)
    for op in ("confirm", "reject"):
        s = sub.add_parser(op)
        s.add_argument("fact")
        s.add_argument("--ref", required=True)
        s.set_defaults(fn=lambda a, op=op: cmd_confirm(a, op))
    s = sub.add_parser("list")
    s.add_argument("--topic")
    s.add_argument("--kind")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("coverage")
    s.add_argument("--require")
    s.add_argument("--record-by", help="registra l'esito in evidence.py come questo agente")
    s.set_defaults(fn=cmd_coverage)
    s = sub.add_parser("check")
    s.add_argument("file")
    s.add_argument("--record-by", help="registra l'esito in evidence.py come questo agente")
    s.set_defaults(fn=cmd_check)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
