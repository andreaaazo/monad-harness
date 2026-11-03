"""Un registro di prova per le prove del cruscotto: `uv run python tests/dashboard_fixture.py <cartella>`.

Un progetto inventato, `officina-e2e`, scritto con il motore vero: più fasi e più istanze, chiamate misurate e
no, un gate approvato, idee, un giudizio, e la storia dei ticket con una revisione bloccata e una rifinitura
rimandata e rifatta. Gli istanti sono fissi, eventi compresi, così le viste mostrano sempre gli stessi numeri.
La cartella si svuota e si riscrive a ogni esecuzione.
"""

from __future__ import annotations

import shutil
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import patch

from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow, GateRow, UsageRow

PROJECT = "officina-e2e"
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
# (minuto, ticket, azione, chi): consegne, accettazioni, il blocco del critico e il rimando del direttore
STEPS = [
    (8, "T-0002", Action.DELIVER, "direction-a"),
    (8, "T-0003", Action.DELIVER, "direction-b"),
    (12, "T-0002", Action.ACCEPT, "design-director"),
    (12, "T-0003", Action.ACCEPT, "design-director"),
    (20, "T-0004", Action.DELIVER, "identity-designer"),
    (24, "T-0004", Action.ACCEPT, "design-director"),
    (36, "T-0005", Action.DELIVER, "identity-designer"),
    (40, "T-0006", Action.BLOCK, "critic"),
    (41, "T-0005", Action.REWORK, "design-director"),
    (45, "T-0005", Action.DELIVER, "identity-designer"),
]


def at(minute: int) -> str:
    return f"2026-11-02T10:{minute:02d}:00+00:00"


def clock(minute: int) -> AbstractContextManager[object]:
    """Il Ledger scrive l'istante di ogni evento con `now()`: qui lo si fissa, un evento alla volta."""
    return patch("agency.ledger.store.now", return_value=at(minute))


def build(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    ledger = Ledger(folder / "ledger.sqlite")
    ledger.set_project(PROJECT, 20.0, "", "high")
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
        minute, instance, ticket, role, phase, cost, duration, ttft, stop = row
        turns[instance] = turns.get(instance, 0) + 1
        ledger.record_usage(
            UsageRow(
                at=at(minute),
                project=PROJECT,
                ticket_id=ticket,
                role=role,
                instance=instance,
                model="claude-opus-5-5",
                input_tokens=400,
                output_tokens=120,
                # Il contesto cresce turno dopo turno, come in un'istanza vera.
                cache_read_tokens=3600 + 1600 * (turns[instance] - 1),
                cache_write_5m_tokens=200,
                cost_usd=cost,
                stop_reason=stop,
                request_id=f"req_e2e_{number}",
                phase=phase if duration is not None else None,
                effort="high" if duration is not None else None,
                duration_ms=duration,
                ttft_ms=ttft,
                reasoning_tokens=60 if duration is not None else None,
            )
        )
    for minute, ticket, action, actor in STEPS:
        with clock(minute):
            ledger.apply(ticket, action, actor)
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
    ledger.engine.dispose()


if __name__ == "__main__":
    build(Path(sys.argv[1]))
    print(f"registro di prova in {sys.argv[1]}")
