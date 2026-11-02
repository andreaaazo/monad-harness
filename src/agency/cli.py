"""Comandi dell'harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

from agency.config import Settings
from agency.doctor import run_checks
from agency.gateway import BudgetExceeded
from agency.gateway.pricing import PRICES
from agency.ledger import Ledger, LedgerOutdated
from agency.ledger.schema import ChainBroken, LedgerMismatch, migrate
from agency.telemetry import report

LOGO_OUTPUTS = ["source/segno.vectorcraft", "exports/segno.svg", "construction.md"]
LOGO_CHECKS = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity", "critique"]}


def _doctor(_: argparse.Namespace) -> int:
    findings = run_checks()
    for item in findings:
        mark = "ok " if item.ok else ("ERR" if item.required else "-- ")
        print(f"{mark} {item.name:18} {item.detail}")
    return 1 if any(f.required and not f.ok for f in findings) else 0


def _verify(_: argparse.Namespace) -> int:
    ok = Ledger(Settings().ledger_path).verify_chain()
    print("registro integro" if ok else "REGISTRO ALTERATO")
    return 0 if ok else 1


def _migrate(_: argparse.Namespace) -> int:
    path = Settings().ledger_path
    if not path.is_file():
        print("Nessun registro da aggiornare: si crea da solo alla prima apertura")
        return 0
    result = migrate(path)
    if result.backup is None:
        print(f"registro già aggiornato, revisione {result.revision}")
    else:
        print(f"registro aggiornato alla revisione {result.revision}. Copia del prima: {result.backup}")
    return 0


def _show(session, project: str) -> int:  # type: ignore[no-untyped-def]
    print(report.render(session.ledger, project))
    for gate in session.pending(project):
        work = session.settings.project_dir(project) / "work"
        print(f"\nIN ATTESA DEL CLIENTE: gate {gate['gate']}")
        for file in gate["files"]:
            print(f"  {work / file}")
        if gate["gate"] == "concept":
            print(f"Proposte: {', '.join(gate['options'])}. Lo studio raccomanda {gate['recommended']}.")
            print(gate["reasons"])
            print(f"agency decide {project} --approve --choice X --text '…'  oppure  --reject --text '…'")
        else:
            print(f"agency decide {project} --approve --text '…'  oppure  --reject --text '…'")
    return 0


def _guarded(project: str, session, action) -> int:  # type: ignore[no-untyped-def]
    """Il budget finito non è un errore: il lavoro resta salvato e la scelta passa al cliente."""
    try:
        result = action()
    except BudgetExceeded as exc:
        print(report.render(session.ledger, project))
        print(f"\nBUDGET FINITO: {exc}. Il lavoro è salvato.")
        print(f"Per continuare: agency budget {project} <nuovo tetto>, poi agency resume {project}")
        return 2
    except anthropic.APIError as exc:
        print(f"\nAPI NON DISPONIBILE: {exc}. Il lavoro è salvato.")
        print(f"Per riprendere: agency resume {project}")
        return 3
    outcome = (result or {}).get("outcome")
    if outcome:
        print(f"Esito: {outcome}")
    return _show(session, project)


def _run(args: argparse.Namespace) -> int:
    from agency.runtime import open_session

    session = open_session(Settings())
    if session.ledger.project(args.project):
        print(f"Il progetto {args.project} esiste già: agency resume {args.project}, o scegli un altro nome")
        return 1
    brief = Path(args.brief)
    if not brief.is_file():
        print(f"Brief non trovato: {brief}")
        return 1
    action = lambda: session.start(  # noqa: E731
        args.project,
        brief,
        LOGO_OUTPUTS,
        LOGO_CHECKS,
        budget=args.budget,
        model=args.model or "",
        effort=args.effort or "",
    )
    return _guarded(args.project, session, action)


def _resume(args: argparse.Namespace) -> int:
    from agency.runtime import open_session

    session = open_session(Settings())
    return _guarded(args.project, session, lambda: session.resume(args.project))


def _decide(args: argparse.Namespace) -> int:
    from agency.runtime import open_session

    session = open_session(Settings())
    waiting = session.pending(args.project)
    if not waiting:
        print(f"{args.project}: nessun gate in attesa del cliente")
        return 1
    gate = waiting[0]
    choice = (args.choice or "").strip().upper()
    if (
        args.approve and gate["gate"] == "concept" and choice not in gate["options"]
    ):  # altrimenti si riesplora
        print(f"Al gate concept scegli una proposta con --choice: {', '.join(gate['options'])}")
        return 1
    action = lambda: session.decide(args.project, args.approve, args.text, choice)  # noqa: E731
    return _guarded(args.project, session, action)


def _budget(args: argparse.Namespace) -> int:
    ledger = Ledger(Settings().ledger_path)
    if ledger.project(args.project) is None:
        print(f"Progetto sconosciuto: {args.project}")
        return 1
    ledger.set_budget(args.project, args.usd)
    print(f"{args.project}: budget portato a {args.usd:.2f} $, spesi {ledger.spent(args.project):.2f} $")
    return 0


def _report(args: argparse.Namespace) -> int:
    print(report.render(Ledger(Settings().ledger_path), args.project))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agency", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="controlla strumenti e configurazione").set_defaults(fn=_doctor)
    sub.add_parser("verify", help="verifica la catena di hash del registro").set_defaults(fn=_verify)
    sub.add_parser("migrate", help="aggiorna il registro, dopo averne fatto una copia").set_defaults(
        fn=_migrate
    )
    run = sub.add_parser("run", help="esegue un brief di logo fino al gate del cliente")
    run.add_argument("project")
    run.add_argument("brief")
    run.add_argument("--budget", type=float, help="tetto di spesa del progetto, in dollari")
    run.add_argument("--model", choices=sorted(PRICES), help="modello per tutti i ruoli")
    run.add_argument("--effort", choices=["low", "medium", "high"], help="effort per tutti i ruoli")
    run.set_defaults(fn=_run)
    resume = sub.add_parser("resume", help="riprende un progetto interrotto")
    resume.add_argument("project")
    resume.set_defaults(fn=_resume)
    decide = sub.add_parser("decide", help="registra la decisione del cliente al gate")
    decide.add_argument("project")
    choice = decide.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    decide.add_argument("--text", required=True)
    decide.add_argument("--choice", help="la lettera dell'idea, al gate concept")
    decide.set_defaults(fn=_decide)
    budget = sub.add_parser("budget", help="cambia il tetto di spesa di un progetto")
    budget.add_argument("project")
    budget.add_argument("usd", type=float)
    budget.set_defaults(fn=_budget)
    show = sub.add_parser("report", help="costi e stato di un progetto")
    show.add_argument("project")
    show.set_defaults(fn=_report)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (LedgerOutdated, LedgerMismatch, ChainBroken) as exc:
        print(f"REGISTRO: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
