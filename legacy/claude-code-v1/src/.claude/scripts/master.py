#!/usr/bin/env python3
"""Master di produzione: ogni mezzo ha il suo file sorgente, e le consegne derivano da lì.

  vettoriale → .vectorcraft · motion → .ecproj · immagine → .pcraft · interfaccia → .figcraft · 3d → .blend

  master.py check work/source/logo.vectorcraft [--record-by <agente>]     # lo apre con la sua CLI
  master.py export work/source/logo.vectorcraft work/exports/logo.svg [-- --artboard 1 --outline-text]
                                                       # esporta con la CLI e registra la derivazione
  master.py link work/source/motion.ecproj work/exports/logo.json --how "file.exportLottie via MCP"
                                                       # per gli export fatti dentro l'app
  master.py status [FILE…]

Registro: .agency/derivations.jsonl (solo aggiunte). Una consegna è derivata se il registro lega la
sua versione attuale alla versione attuale del master: un export senza legame, o un master
modificato dopo, viene rifiutato da ticket.py alla consegna.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
LOG = ROOT / ".agency/derivations.jsonl"
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Estensioni delle consegne per mezzo: i file in work/proofs/ sono prove, non consegne.
MEDIA = {
    "vettoriale": {"master": ".vectorcraft", "tool": "VectorCraft", "exports": (".svg", ".pdf", ".eps", ".ai", ".png")},
    "motion": {"master": ".ecproj", "tool": "EffectCraft", "exports": (".mp4", ".mov", ".webm", ".gif", ".json", ".lottie")},
    "immagine": {"master": ".pcraft", "tool": "PhotoCraft", "exports": (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".psd")},
    "interfaccia": {"master": ".figcraft", "tool": "FigCraft", "exports": (".png", ".svg", ".pdf", ".webp", ".jpg")},
    "3d": {"master": ".blend", "tool": "Blender", "exports": ()},
}


def rel(p):
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


def cli(cmd, timeout=120):
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return r.returncode, r.stdout if r.returncode == 0 else (r.stderr or r.stdout)


def problem(path):
    """None se il master si apre e contiene lavoro; altrimenti il motivo."""
    full = ROOT / path
    if not full.exists():
        return "non esiste"
    ext = full.suffix.lower()
    if ext == ".vectorcraft":
        code, out = cli(["vectorcraft-cli", "info", full])
        if code:
            return f"VectorCraft non lo apre: {out.strip()[:200]}"
        return None if json.loads(out).get("info", {}).get("objects", 0) > 1 else "documento vuoto"
    if ext == ".figcraft":
        code, out = cli(["figcraft-cli", "info", full, "--json"])
        if code:
            return f"FigCraft non lo apre: {out.strip()[:200]}"
        frames = sum(p.get("topLevel", 0) for p in json.loads(out).get("pages", []))
        return None if frames else "documento vuoto: nessun frame"
    if ext == ".pcraft":
        code, out = cli(["photocraft-cli", "info", full])
        if code:
            return f"PhotoCraft non lo apre: {out.strip()[:200]}"
        return None if json.loads(out).get("layers") else "documento vuoto: nessun livello"
    if ext == ".ecproj":
        code, out = cli(["effectcraft-cli", "info", "--project", full, "--json"])
        if code:
            return f"EffectCraft non lo apre: {out.strip()[:200]}"
        return None if (json.loads(out).get("activeComp") or {}).get("layers") else "progetto vuoto: nessun livello"
    if ext == ".blend":
        with open(full, "rb") as fh:
            head = fh.read(8)
        return None if head[:7] == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd" or head[:2] == b"\x1f\x8b" else "non è un file Blender"
    return f"{ext}: non è un master dello studio"


def entries():
    if not LOG.exists():
        return []
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


def derived_problem(export, masters):
    """None se la versione attuale di `export` deriva dalla versione attuale di un master indicato."""
    current = sha(export)
    links = [e for e in entries() if e["export"] == export and e["export_sha"] == current and e["master"] in masters]
    if not links:
        return "non risulta esportato da un master del ticket (master.py export)"
    if any((ROOT / e["master"]).exists() and sha(e["master"]) == e["master_sha"] for e in links):
        return None
    return "il master è cambiato dopo l'export: riesporta"


def register(master, out, how):
    e = {"ts": datetime.now().isoformat(timespec="seconds"), "master": master, "master_sha": sha(master),
         "export": out, "export_sha": sha(out), "how": how}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def cmd_check(a):
    f = rel(a.file)
    why = problem(f)
    print(f"{f}: {why or 'ok'}")
    if a.record_by and (ROOT / f).exists():
        import evidence
        evidence.record_auto(f, "master_open", "FAIL" if why else "PASS", a.record_by, note=why)
    sys.exit(1 if why else 0)


def cmd_export(a):
    m, out = rel(a.master), rel(a.out)
    if problem(m):
        sys.exit(f"{m}: {problem(m)}")
    (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
    ext = Path(m).suffix.lower()
    src, dst = ROOT / m, ROOT / out
    if ext == ".vectorcraft":
        cmd = ["vectorcraft-cli", "convert", src, dst, *a.extra]
    elif ext == ".figcraft":
        cmd = ["figcraft-cli", "export", src, "-o", dst, *a.extra]
    elif ext == ".pcraft":
        cmd = ["photocraft-cli", "convert", src, dst, *a.extra]
    elif ext == ".ecproj":
        cmd = ["effectcraft-cli", "render", "--project", src, "--out", dst, *a.extra]
    else:
        sys.exit(f"{ext}: export non previsto, usa master.py link")
    code, text = cli(cmd, timeout=1800)
    if code or not dst.exists():
        sys.exit(f"export fallito: {text.strip()[:400]}")
    register(m, out, " ".join(str(c) for c in cmd[:2]))
    print(f"esportato {out} da {m}")


def cmd_link(a):
    m, out = rel(a.master), rel(a.out)
    for f in (m, out):
        if not (ROOT / f).exists():
            sys.exit(f"file inesistente: {f}")
    if (ROOT / out).stat().st_mtime < (ROOT / m).stat().st_mtime:
        sys.exit(f"{out} è più vecchio del master: riesporta dalla versione attuale")
    register(m, out, a.how)
    print(f"legato {out} a {m}")


def cmd_status(a):
    files = {rel(f) for f in a.files}
    seen = {}
    for e in entries():
        if not files or e["export"] in files:
            seen[e["export"]] = e
    for f, e in sorted(seen.items()):
        state = derived_problem(f, [e["master"]]) if (ROOT / f).exists() else "mancante"
        print(f"{'ok' if not state else 'SCADUTO'}  {f} ← {e['master']}{'' if not state else '  ' + state}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("file")
    c.add_argument("--record-by")
    c.set_defaults(fn=cmd_check)
    e = sub.add_parser("export")
    e.add_argument("master")
    e.add_argument("out")
    e.add_argument("extra", nargs="*", help="opzioni della CLI, dopo --")
    e.set_defaults(fn=cmd_export)
    li = sub.add_parser("link")
    li.add_argument("master")
    li.add_argument("out")
    li.add_argument("--how", required=True)
    li.set_defaults(fn=cmd_link)
    s = sub.add_parser("status")
    s.add_argument("files", nargs="*")
    s.set_defaults(fn=cmd_status)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
