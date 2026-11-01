#!/usr/bin/env python3
"""Lock di scrittura per i server Craft condivisi (un solo autore per server).

  craft_lock.py acquire vectorcraft <titolare> <documento> [--ticket T-0007] [--ttl 90]
  craft_lock.py renew   vectorcraft <titolare>
  craft_lock.py release vectorcraft <titolare> [--force]
  craft_lock.py status

Il titolare è il nome dell'agente (es. identity-designer) o "router" per la sessione
principale. L'hook craft-guard blocca le chiamate MCP Craft senza un lock valido.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
LOCKS = ROOT / ".claude/runtime/locks"
SERVERS = ("vectorcraft", "effectcraft", "figcraft", "photocraft")


def path(server):
    return LOCKS / f"{server}.json"


def read(server):
    try:
        data = json.loads(path(server).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data


def valid(lock):
    return lock is not None and lock.get("expires_at", 0) > time.time()


def write_atomic(server, data, exclusive):
    LOCKS.mkdir(parents=True, exist_ok=True)
    if exclusive:
        fd = os.open(path(server), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return
    tmp = path(server).with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path(server))


def fmt(server, lock):
    if not lock:
        return f"{server}: libero"
    left = int((lock["expires_at"] - time.time()) / 60)
    state = f"scade tra {left} min" if left >= 0 else "SCADUTO"
    return f"{server}: {lock['holder']} su {lock['document']} (ticket {lock.get('ticket') or '-'}, {state})"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("server", choices=SERVERS)
    a.add_argument("holder")
    a.add_argument("document")
    a.add_argument("--ticket")
    a.add_argument("--ttl", type=int, default=90, help="minuti")
    r = sub.add_parser("renew")
    r.add_argument("server", choices=SERVERS)
    r.add_argument("holder")
    r.add_argument("--ttl", type=int, default=90)
    rel = sub.add_parser("release")
    rel.add_argument("server", choices=SERVERS)
    rel.add_argument("holder")
    rel.add_argument("--force", action="store_true", help="solo il router, dopo aver verificato che il titolare ha finito")
    sub.add_parser("status")
    args = p.parse_args()

    if args.cmd == "status":
        for s in SERVERS:
            print(fmt(s, read(s)))
        return

    lock = read(args.server)
    now = time.time()
    if args.cmd == "acquire":
        if valid(lock) and lock["holder"] != args.holder:
            sys.exit(f"OCCUPATO — {fmt(args.server, lock)}. Attendi o chiedi al router.")
        data = {"holder": args.holder, "document": args.document, "ticket": args.ticket,
                "acquired_at": now, "expires_at": now + args.ttl * 60}
        if lock is not None and (not valid(lock) or lock["holder"] == args.holder):
            write_atomic(args.server, data, exclusive=False)
        else:
            try:
                write_atomic(args.server, data, exclusive=True)
            except FileExistsError:
                sys.exit(f"OCCUPATO — {fmt(args.server, read(args.server))}")
        print("ACQUISITO — " + fmt(args.server, data))
    elif args.cmd == "renew":
        if not lock or lock["holder"] != args.holder:
            sys.exit(f"non sei il titolare — {fmt(args.server, lock)}")
        lock["expires_at"] = now + args.ttl * 60
        write_atomic(args.server, lock, exclusive=False)
        print("RINNOVATO — " + fmt(args.server, lock))
    elif args.cmd == "release":
        if lock and lock["holder"] != args.holder and not args.force:
            sys.exit(f"non sei il titolare — {fmt(args.server, lock)}")
        try:
            path(args.server).unlink()
        except FileNotFoundError:
            pass
        print(f"RILASCIATO — {args.server}")


if __name__ == "__main__":
    main()
