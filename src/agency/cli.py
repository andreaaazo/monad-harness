"""Comandi dell'harness."""

from __future__ import annotations

import argparse
import getpass
import math
import random
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import anthropic

from agency.artifacts import FileStore, keeping
from agency.config import Settings
from agency.contracts.artifact import Origin
from agency.contracts.gate import ConceptGate
from agency.doctor import run_checks
from agency.evaluation import blind, board
from agency.gateway import BudgetExceeded
from agency.gateway.pricing import PRICES
from agency.insights import application as insights
from agency.insights.adapters.projection import SqliteProjection
from agency.insights.adapters.registry import ReadOnlyRegistry
from agency.insights.adapters.traces import JsonlTraces
from agency.insights.adapters.transcripts import JsonlTranscripts
from agency.insights.views import ProjectReport
from agency.ledger import Ledger, LedgerOutdated
from agency.ledger.schema import ChainBroken, LedgerMismatch, migrate
from agency.ledger.store import now
from agency.telemetry import report

if TYPE_CHECKING:  # la sessione carica il motore: i comandi leggeri non la importano
    from agency.runtime import Session

LOGO_OUTPUTS = ["source/segno.vectorcraft", "exports/segno.svg", "construction.md"]
LOGO_CHECKS = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity", "critique"]}


def _doctor(_: argparse.Namespace) -> int:
    findings = run_checks()
    for item in findings:
        mark = "ok " if item.ok else ("ERR" if item.required else "-- ")
        print(f"{mark} {item.name:18} {item.detail}")
    return 1 if any(f.required and not f.ok for f in findings) else 0


def _verify(_: argparse.Namespace) -> int:
    settings = Settings()
    ledger = Ledger(settings.ledger_path)
    ok = ledger.verify_chain()
    print("registro integro" if ok else "REGISTRO ALTERATO")
    broken = keeping.damaged(FileStore(settings.artifacts_dir), ledger)
    print(report.render_damaged(broken) if broken else f"artefatti integri: {keeping.versions(ledger)}")
    return 0 if ok and not broken else 1


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


def _report_of(settings: Settings, project: str) -> ProjectReport:
    """Il rapporto passa da insights, come il cruscotto: la proiezione si rifà se il registro è cambiato."""
    projection = SqliteProjection(settings.insights_path)
    insights.current(
        ReadOnlyRegistry(settings.ledger_path),
        JsonlTraces(settings.traces_path),
        JsonlTranscripts(settings.layout),
        projection,
        now(),
    )
    return insights.report(projection, project)


def _show(session: Session, project: str) -> int:
    print(report.render(_report_of(session.settings, project)))
    for gate in session.pending(project):
        work = session.settings.project_dir(project) / "work"
        print(f"\nIN ATTESA DEL CLIENTE: gate {gate.gate}")
        for file in gate.files:
            print(f"  {work / file}")
        if isinstance(gate, ConceptGate):
            print(f"Proposte: {', '.join(gate.options)}. Lo studio raccomanda {gate.recommended}.")
            print(gate.reasons)
            print(f"agency decide {project} --approve --choice X --text '…'  oppure  --reject --text '…'")
        else:
            print(f"agency decide {project} --approve --text '…'  oppure  --reject --text '…'")
    return 0


def _guarded(project: str, session: Session, action: Callable[[], str]) -> int:
    """Il budget finito non è un errore: il lavoro resta salvato e la scelta passa al cliente."""
    try:
        outcome = action()
    except BudgetExceeded as exc:
        print(report.render(_report_of(session.settings, project)))
        print(f"\nBUDGET FINITO: {exc}. Il lavoro è salvato.")
        print(f"Per continuare: agency budget {project} <nuovo tetto>, poi agency resume {project}")
        return 2
    except anthropic.APIError as exc:
        print(f"\nAPI NON DISPONIBILE: {exc}. Il lavoro è salvato.")
        print(f"Per riprendere: agency resume {project}")
        return 3
    if outcome:
        print(f"Esito: {outcome}")
    return _show(session, project)


def _dollars(text: str) -> float:
    """Un tetto di spesa: un importo positivo e finito. Zero, negativi, `nan` e `inf` non sono tetti."""
    try:
        amount = float(text)
    except ValueError:
        amount = math.nan
    if not math.isfinite(amount) or amount <= 0:
        raise argparse.ArgumentTypeError(f"{text!r}: il tetto è un importo positivo in dollari, come 30")
    return amount


def _run(args: argparse.Namespace) -> int:
    from agency.runtime import BriefNotUtf8, open_session

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
    try:
        return _guarded(args.project, session, action)
    except BriefNotUtf8:
        print(f"Il brief {brief} non è UTF-8: salvalo in UTF-8 e riprova")
        return 1


def _resume(args: argparse.Namespace) -> int:
    from agency.runtime import NothingToResume, open_session

    if Ledger(Settings().ledger_path).project(args.project) is None:
        print(f"Progetto sconosciuto: {args.project}")
        return 1
    session = open_session(Settings())
    try:
        return _guarded(args.project, session, lambda: session.resume(args.project))
    except NothingToResume:
        print(f"{args.project}: nessun lavoro salvato da riprendere")
        return 1


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
        args.approve and isinstance(gate, ConceptGate) and choice not in gate.options
    ):  # altrimenti si riesplora
        print(f"Al gate concept scegli una proposta con --choice: {', '.join(gate.options)}")
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
    view = _report_of(Settings(), args.project)
    print(view.model_dump_json(indent=2) if args.json else report.render(view))
    return 0


def _runs(args: argparse.Namespace) -> int:
    print(report.render_runs(Ledger(Settings().ledger_path), args.project))
    return 0


def _compare(args: argparse.Namespace) -> int:
    ledger = Ledger(Settings().ledger_path)
    first, second = ledger.run(args.first), ledger.run(args.second)
    if first is None or second is None:
        missing = [f"#{seq}" for seq, row in ((args.first, first), (args.second, second)) if row is None]
        print(f"Esecuzione sconosciuta: {', '.join(missing)}. Quelle di un progetto: agency runs <progetto>")
        return 1
    print(report.render_comparison(first, second))
    return 0


def _judge(args: argparse.Namespace) -> int:
    settings = Settings()
    ledger = Ledger(settings.ledger_path)
    store = FileStore(settings.artifacts_dir)
    try:
        found = blind.candidates([Path(path) for path in args.files], settings.projects_dir)
    except blind.CannotCompare as exc:
        print(f"Confronto non possibile: {exc}")
        return 1
    comparison = blind.comparison_id()
    assigned = blind.assign(found, random.SystemRandom())
    folder = settings.data_dir / "blind" / comparison
    try:
        copies = blind.lay_out(assigned, folder)
        sheet = board.lay_board(dict(zip(assigned, copies, strict=True)), folder, board.vectorcraft())
        print(f"Confronto alla cieca di {len(copies)} file, nella cartella {folder.resolve()}:")
        if sheet is not None:
            print(f"  {sheet.name}  {board.SHOWN}")
        for copy in copies:
            print(f"  {copy.name}")
        if sheet is None:
            kind = copies[0].suffix
            print(f"Per i file {kind} non c'è una tavola: si guardano come sono, anche a misure diverse.")
        print("Guarda e rispondi. Da dove vengono si vede solo dopo il giudizio.")
        judgment = blind.interview(list(assigned), input, args.judge)
        altered = blind.changed(assigned, copies)
        if altered:
            raise blind.CannotCompare(f"le copie {', '.join(altered)} sono cambiate durante il giudizio")
        for item, copy in zip(assigned.values(), copies, strict=True):  # si conserva ciò che si è guardato
            judged = item.judged
            keeping.keep(
                store,
                ledger,
                copy.parent,
                {judged.file: copy.name},
                project=judged.project,
                origin=Origin.JUDGMENT,
                ticket_id="",
                run=None,
            )
    except blind.CannotCompare as exc:
        print(f"Confronto non possibile: {exc}. Nulla registrato")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nGiudizio interrotto: nulla registrato")
        return 1
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    ledger.record_judgment(comparison, judgment, {letter: item.judged for letter, item in assigned.items()})
    print(report.render_reveal(ledger.comparison(comparison)))
    return 0


def _artifacts(args: argparse.Namespace) -> int:
    print(report.render_artifacts(Ledger(Settings().ledger_path).artifacts(args.project), args.project))
    return 0


def _restore(args: argparse.Namespace) -> int:
    settings = Settings()
    ledger, store = Ledger(settings.ledger_path), FileStore(settings.artifacts_dir)
    destination = Path(args.destination)
    try:
        rows = keeping.restore(store, ledger, args.hash, destination)
    except keeping.CannotRestore as exc:
        print(f"Ripristino non possibile: {exc}")
        return 1
    print(report.render_restored(rows, str(destination)))
    return 0


def _insights(_: argparse.Namespace) -> int:
    """Legge il registro in sola lettura: si può usare anche mentre il motore lavora."""
    settings = Settings()
    registry, traces = ReadOnlyRegistry(settings.ledger_path), JsonlTraces(settings.traces_path)
    transcripts = JsonlTranscripts(settings.layout)
    built = insights.rebuild(registry, traces, transcripts, SqliteProjection(settings.insights_path), now())
    print(report.render_provenance(built, str(settings.insights_path)))
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
    run.add_argument(
        "--budget",
        type=_dollars,
        required=True,
        help="tetto di spesa del progetto, in dollari: lo dichiara chi avvia, non ha un default",
    )
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
    budget.add_argument("usd", type=_dollars, help="il nuovo tetto, in dollari")
    budget.set_defaults(fn=_budget)
    show = sub.add_parser("report", help="costi, fasi e stato di un progetto")
    show.add_argument("project")
    show.add_argument("--json", action="store_true", help="il modello del rapporto, lo stesso del cruscotto")
    show.set_defaults(fn=_report)
    runs = sub.add_parser("runs", help="le esecuzioni di un progetto e cosa è cambiato dall'una all'altra")
    runs.add_argument("project")
    runs.set_defaults(fn=_runs)
    compare = sub.add_parser("compare", help="cosa cambia tra due esecuzioni, anche di progetti diversi")
    compare.add_argument("first", type=int, help="numero dell'esecuzione, da agency runs")
    compare.add_argument("second", type=int)
    compare.set_defaults(fn=_compare)
    judge = sub.add_parser("judge", help="giudizio alla cieca: file anonimi, poi il voto, poi l'origine")
    judge.add_argument("files", nargs="+", help="i file da confrontare, dello stesso tipo")
    judge.add_argument(
        "--judge", default=getpass.getuser(), help="chi giudica; di solito l'utente del sistema"
    )
    judge.set_defaults(fn=_judge)
    kept = sub.add_parser("artifacts", help="le versioni conservate di un progetto, con il loro hash")
    kept.add_argument("project")
    kept.set_defaults(fn=_artifacts)
    restore = sub.add_parser("restore", help="riporta una versione conservata in un file nuovo")
    restore.add_argument("hash", help="lo sha256, o le sue prime cifre (almeno 8)")
    restore.add_argument("destination", help="il file da creare: se esiste già, non si tocca")
    restore.set_defaults(fn=_restore)
    sub.add_parser(
        "insights", help="rigenera la proiezione per report e cruscotto, senza scrivere il registro"
    ).set_defaults(fn=_insights)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (LedgerOutdated, LedgerMismatch, ChainBroken, insights.RegistryNotReadable) as exc:
        print(f"REGISTRO: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
