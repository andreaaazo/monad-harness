"""Un registro di prova per le prove del cruscotto: `uv run python tests/dashboard_fixture.py <cartella>`.

Un progetto inventato, `officina-e2e`, scritto con il motore vero: più fasi e più istanze, chiamate misurate e
no, un gate approvato, idee, un giudizio, la storia dei ticket con una revisione bloccata e una rifinitura
rimandata e rifatta, prove FAIL e PASS, trascrizioni con due strumenti che dicono no, e due esecuzioni con
la loro impronta. Accanto, `officina-prima`: lo stesso lavoro il giorno prima, con un'impronta diversa e un
giudizio alla cieca che mette i due segni a confronto. Gli istanti sono fissi, eventi compresi, così le
viste mostrano sempre gli stessi numeri. La cartella si svuota e si riscrive a ogni esecuzione.
"""

from __future__ import annotations

import base64
import shutil
import struct
import sys
import zlib
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import patch

from agency.agents.transcript import Transcript
from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.contracts.layout import DataLayout
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.run import Fingerprint, RunCommand
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow, EvidenceRow, GateRow, UsageRow

PROJECT = "officina-e2e"
BEFORE = "officina-prima"
DAY, DAY_BEFORE = "2026-11-02", "2026-11-01"
# (minuto, istanza, ticket, ruolo, fase, costo, durata in ms o None se non misurata, TTFT in ms, stop_reason)
CALLS = [
    (0, "T-0001-a1-plan", "T-0001", "design-director", "director-plan", 0.40, 21000, 9000, "tool_use"),
    (2, "T-0002-a1", "T-0002", "direction-a", "explorer", 0.90, 9000, 2100, "tool_use"),
    (2, "T-0003-a1", "T-0003", "direction-b", "explorer", 0.80, 8600, 1900, "tool_use"),
    (6, "T-0002-a1", "T-0002", "direction-a", "explorer", 1.10, 9800, 2300, "tool_use"),
    (7, "T-0003-a1", "T-0003", "direction-b", "explorer", 0.70, None, None, "tool_use"),
    (12, "T-0001-a1-select", "T-0001", "design-director", "director-select", 0.30, 4600, 2600, "tool_use"),
    (15, "T-0004-a1", "T-0004", "identity-designer", "proposer", 1.60, 11000, 3200, "max_tokens"),
    (24, "T-0001-a1-present", "T-0001", "design-director", "director-present", 0.20, 8200, 2900, "end_turn"),
    (31, "T-0005-a1", "T-0005", "identity-designer", "finisher", 2.40, 9400, 2600, "tool_use"),
    (38, "T-0006-a1", "T-0006", "critic", "critic", 0.30, 7800, 2400, "tool_use"),
    (44, "T-0005-a2", "T-0005", "identity-designer", "finisher", 2.10, 9100, 2500, "tool_use"),
]
# (minuto di apertura, titolo, tipo, a chi, prompt)
TICKETS = [
    (0, "Consegna officina-e2e", TicketType.DELIVERY, "design-director", ""),
    (1, "Esplorazione a", TicketType.SKETCH, "direction-a", "explorer"),
    (1, "Esplorazione b", TicketType.SKETCH, "direction-b", "explorer"),
    (13, "Proposta X r1", TicketType.PROPOSAL, "identity-designer", "proposer"),
    (30, "Rifinitura X", TicketType.PRODUCTION, "identity-designer", "finisher"),
    (37, "Revisione segno X", TicketType.REVIEW, "critic", ""),
]
BLOCKED = "Il contratto chiede review/critica.md, ma posso scrivere solo in reviews/.\nIl referto è pronto."
REWORKED = "La coda sparisce a 16 px: ingrossala di 2 unità."
# (minuto, ticket, azione, chi, nota): consegne, accettazioni, il blocco del critico, il rimando del direttore
STEPS = [
    (8, "T-0002", Action.DELIVER, "direction-a", ""),
    (8, "T-0003", Action.DELIVER, "direction-b", ""),
    (12, "T-0002", Action.ACCEPT, "design-director", ""),
    (12, "T-0003", Action.ACCEPT, "design-director", ""),
    (20, "T-0004", Action.DELIVER, "identity-designer", "Le parole di una consegna restano nel registro"),
    (24, "T-0004", Action.ACCEPT, "design-director", ""),
    (36, "T-0005", Action.DELIVER, "identity-designer", ""),
    (40, "T-0006", Action.BLOCK, "critic", BLOCKED),
    (41, "T-0005", Action.REWORK, "design-director", REWORKED),
    (45, "T-0005", Action.DELIVER, "identity-designer", ""),
]
# (minuto, ticket, file, controllo, esito, chi firma, nota)
CHECKS = [
    (7, "T-0002", "foglio-a.png", "master_open", "PASS", "direction-a", ""),
    (19, "T-0004", "proposta.svg", "svg_audit", "PASS", "identity-designer", ""),
    (
        35,
        "T-0005",
        "exports/segno.svg",
        "svg_audit",
        "FAIL",
        "identity-designer",
        "3 nodi sottotracciati\nnodi=24",
    ),
    (39, "T-0006", "exports/segno.svg", "visual_review", "FAIL", "critic", "La coda sparisce a 16 px"),
    (43, "T-0005", "exports/segno.svg", "svg_audit", "PASS", "identity-designer", ""),
]
DELIVERY_REFUSED = "consegna rifiutata:\nexports/segno.svg: 'svg_audit' è FAIL"
WRITE_REFUSED = "un revisore scrive solo in reviews/: non modifica il lavoro che giudica"
THOUGHT = "Guardo prima il foglio intero, poi il dettaglio"
REMINDER = "Ricorda di consegnare con deliver"
SVG = b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"


def png(width: int, height: int) -> bytes:
    """Una PNG vera, di un solo colore: il browser la deve poter disegnare."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"\x2a\x78\xd6\xff" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def picture(media_type: str, data: bytes) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(data).decode()},
    }


# Le trascrizioni: per ogni istanza, i turni del modello. Un turno è la chiamata che lo ha prodotto (il
# numero della riga di usage, per il suo request_id; None in una trascrizione di prima di M1.6), ciò che il
# modello ha pensato e scritto, gli strumenti chiesti col rifiuto o col risultato, i messaggi dell'harness.
Turn = tuple[int | None, list[str], list[str], list[tuple[str, str | None, list[dict]]], list[str]]
TRANSCRIPTS: dict[str, tuple[list[Turn], tuple[OutcomeState, str] | None]] = {
    "T-0002-a1": (
        [
            (2, [THOUGHT], ["Apro il foglio"], [("view_image", None, [picture("image/png", png(4, 2))])], []),
            (4, [], [], [("view_image", None, [picture("image/svg+xml", SVG)])], [REMINDER]),
        ],
        (OutcomeState.DELIVERED, "Foglio consegnato"),
    ),
    "T-0005-a1": (
        [(9, [], [], [("deliver", DELIVERY_REFUSED, []), ("render", None, []), ("deliver", None, [])], [])],
        (OutcomeState.DELIVERED, ""),
    ),
    # Di prima di M1.6: senza request_id, i turni si legano alle chiamate per ordine.
    "T-0006-a1": ([(None, [], [], [("write_file", WRITE_REFUSED, []), ("block", None, [])], [])], None),
    # La sola risposta, tagliata dal limite di token, non entra in trascrizione.
    "T-0004-a1": ([], None),
}


def at(minute: int, day: str = DAY) -> str:
    return f"{day}T10:{minute:02d}:00+00:00"


def clock(minute: int, day: str = DAY) -> AbstractContextManager[object]:
    """Il Ledger scrive l'istante di ogni evento con `now()`: qui lo si fissa, un evento alla volta."""
    return patch("agency.ledger.store.now", return_value=at(minute, day))


# Le impronte: officina-prima esplorava con 5 direzioni e un altro prompt del designer.
PRINT_BEFORE = Fingerprint(
    model="",
    effort="high",
    explorer_effort="high",
    proposal_effort="high",
    explorers=5,
    max_parallel=5,
    prompts={"prompts/roles/identity-designer.md": "1" * 64, "prompts/roles/critic.md": "3" * 64},
    registry={"registry/roles.json": "4" * 64},
    code={"src/agency/cli.py": "5" * 64},
    lock="6" * 64,
    python="3.13.1",
    tools={"vectorcraft-cli": "vectorcraft 1.0"},
)
PRINT_AFTER = PRINT_BEFORE.model_copy(
    update={
        "explorers": 3,
        "prompts": {"prompts/roles/identity-designer.md": "2" * 64, "prompts/roles/critic.md": "3" * 64},
    }
)
# officina-prima: (minuto, istanza, ticket, fase, costo), tutte dell'identity-designer tranne il piano
CALLS_BEFORE = [
    (0, "T-0007-a1-plan", "T-0007", "design-director", "director-plan", 0.50),
    (3, "T-0008-a1", "T-0008", "identity-designer", "finisher", 3.00),
    (9, "T-0008-a1", "T-0008", "identity-designer", "finisher", 2.50),
]


def usage(
    number: int,
    project: str,
    day: str,
    row: tuple,
    turn: int,
    run: int,
    *,
    stop_reason: str,
    phase: str | None = None,
    duration_ms: int | None = None,
    ttft_ms: int | None = None,
) -> UsageRow:
    """Una chiamata della prova. Una chiamata misurata ha fase, effort, durata, TTFT e ragionamento."""
    minute, instance, ticket, role, _, cost = row[:6]
    measured = duration_ms is not None
    return UsageRow(
        at=at(minute, day),
        project=project,
        ticket_id=ticket,
        role=role,
        instance=instance,
        model="claude-opus-5-5",
        input_tokens=400,
        output_tokens=120,
        # Il contesto cresce turno dopo turno, come in un'istanza vera.
        cache_read_tokens=3600 + 1600 * (turn - 1),
        cache_write_5m_tokens=200,
        cost_usd=cost,
        stop_reason=stop_reason,
        request_id=f"req_e2e_{number}",
        run=run,
        phase=phase if measured else None,
        effort="high" if measured else None,
        duration_ms=duration_ms,
        ttft_ms=ttft_ms,
        reasoning_tokens=60 if measured else None,
    )


def build_before(ledger: Ledger) -> int:
    """Il progetto di prima: un piano e una rifinitura consegnata, con la sua esecuzione."""
    ledger.set_project(BEFORE, 20.0, "", "high")
    with clock(0, DAY_BEFORE):
        run = ledger.record_run(BEFORE, RunCommand.RUN, PRINT_BEFORE)
    for minute, title, kind, assignee, prompt in [
        (0, "Consegna officina-prima", TicketType.DELIVERY, "design-director", ""),
        (2, "Rifinitura X", TicketType.PRODUCTION, "identity-designer", "finisher"),
    ]:
        spec = TicketSpec(
            title=title,
            request="Prova del cruscotto",
            type=kind,
            sender="router" if kind is TicketType.DELIVERY else "design-director",
            assignee=assignee,
            outputs=["segno.svg"],
            checks={"*.svg": ["svg_audit"]},
            media=[] if kind is TicketType.DELIVERY else [Medium.VECTOR],
            prompt=prompt,
        )
        with clock(minute, DAY_BEFORE):
            ledger.open(spec, BEFORE)
    turns: dict[str, int] = {}
    for number, row in enumerate(CALLS_BEFORE, start=100):
        turns[row[1]] = turns.get(row[1], 0) + 1
        ledger.record_usage(
            usage(number, BEFORE, DAY_BEFORE, row, turns[row[1]], run, stop_reason="end_turn")
        )
    with clock(10, DAY_BEFORE):
        ledger.apply("T-0008", Action.DELIVER, "identity-designer")
    return run


def write_transcripts(layout: DataLayout) -> None:
    """Con la classe del motore: il formato è quello che il motore scrive davvero."""
    for instance, (turns, closed) in TRANSCRIPTS.items():
        transcript = Transcript(layout.transcript(PROJECT, instance))
        transcript.append({"role": "user", "content": "Prova del cruscotto"})
        for number, (call, thoughts, words, tools, notes) in enumerate(turns, start=1):
            uses = [
                {
                    "type": "tool_use",
                    "id": f"{instance}-{number}-{index}",
                    "name": name,
                    "input": {"turno": number},
                }
                for index, (name, _, _) in enumerate(tools)
            ]
            content = [
                *({"type": "thinking", "thinking": thought, "signature": "firma"} for thought in thoughts),
                *({"type": "text", "text": text} for text in words),
                *uses,
            ]
            transcript.append(
                {"role": "assistant", "content": content},
                request_id=f"req_e2e_{call}" if call is not None else None,
            )
            answers = [
                {
                    "type": "tool_result",
                    "tool_use_id": use["id"],
                    "content": refusal or [{"type": "text", "text": "ok"}, *images],
                }
                | ({"is_error": True} if refusal is not None else {})
                for use, (_, refusal, images) in zip(uses, tools, strict=True)
            ]
            transcript.append({"role": "user", "content": answers})
            for note in notes:
                transcript.append({"role": "user", "content": note})
        if closed is not None:
            transcript.finish(Outcome(state=closed[0], note=closed[1]))


def build(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    ledger = Ledger(folder / "ledger.sqlite")
    ledger.set_project(PROJECT, 20.0, "", "high")
    # Il lavoro fino al gate con `run`, il resto con `decide`: stessa impronta.
    with clock(0):
        started = ledger.record_run(PROJECT, RunCommand.RUN, PRINT_AFTER)
    with clock(30):
        decided = ledger.record_run(PROJECT, RunCommand.DECIDE, PRINT_AFTER)
    for minute, title, kind, assignee, prompt in TICKETS:
        spec = TicketSpec(
            title=title,
            request="Prova del cruscotto",
            type=kind,
            sender="router" if kind is TicketType.DELIVERY else "design-director",
            assignee=assignee,
            outputs=["segno.svg"],
            checks={"*.svg": ["svg_audit"]},
            media=[] if kind in {TicketType.DELIVERY, TicketType.REVIEW} else [Medium.VECTOR],
            prompt=prompt,
        )
        with clock(minute):
            ledger.open(spec, PROJECT)
    turns: dict[str, int] = {}
    for number, row in enumerate(CALLS, start=1):
        minute, instance, _, _, phase, _, duration, ttft, stop = row
        turns[instance] = turns.get(instance, 0) + 1
        run = started if minute < 30 else decided
        ledger.record_usage(
            usage(
                number,
                PROJECT,
                DAY,
                row,
                turns[instance],
                run,
                stop_reason=stop,
                phase=phase,
                duration_ms=duration,
                ttft_ms=ttft,
            )
        )
    for minute, ticket, action, actor, note in STEPS:
        with clock(minute):
            ledger.apply(ticket, action, actor, note=note)
    for minute, ticket, file, check, result, signer, note in CHECKS:
        ledger.add_evidence(
            EvidenceRow(
                at=at(minute),
                project=PROJECT,
                file=file,
                sha256="d" * 64,
                check_name=check,
                result=result,
                signer=signer,
                ticket_id=ticket,
                note=note,
            )
        )
    write_transcripts(DataLayout(folder))
    ledger.add_gate(
        GateRow(at=at(30), project=PROJECT, gate="concept", approved=True, choice="X", files_json="{}")
    )
    ledger.add_concept(
        ConceptRow(project=PROJECT, round=1, letter="a", lever="il nome", idea_ticket="T-0002", anon="X")
    )
    rating = Rating(letter="A", level=Level.GOOD, specific=True, why="Si legge da lontano")
    ledger.record_judgment(
        "e2e",
        Judgment(judge="prova", ratings=[rating]),
        {"A": Judged(project=PROJECT, file="segno.svg", sha256="c" * 64)},
    )
    build_before(ledger)
    # Il confronto alla cieca fra i due segni: chi giudica vede solo A e B.
    ledger.record_judgment(
        "prima-dopo",
        Judgment(
            judge="prova",
            ratings=[
                Rating(letter="A", level=Level.ORDINARY, specific=False, why="Potrebbe essere di chiunque"),
                Rating(
                    letter="B", level=Level.GOOD, specific=True, why="La coda dice il nome\nanche a 16 px"
                ),
            ],
            best="B",
        ),
        {
            "A": Judged(project=BEFORE, file="segno.svg", sha256="a" * 64),
            "B": Judged(project=PROJECT, file="exports/segno.svg", sha256="b" * 64),
        },
    )
    ledger.engine.dispose()


if __name__ == "__main__":
    build(Path(sys.argv[1]))
    print(f"registro di prova in {sys.argv[1]}")
