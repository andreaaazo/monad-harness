"""Un registro di prova per le prove del cruscotto: `uv run python tests/dashboard_fixture.py <cartella>`.

Un progetto inventato, `officina-e2e`, scritto con il motore vero: più fasi e più istanze, chiamate misurate e
no, un gate approvato, idee e un giudizio. Gli istanti sono fissi, così le viste mostrano sempre gli stessi
numeri. La cartella si svuota e si riscrive a ogni esecuzione.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow, GateRow, UsageRow

PROJECT = "officina-e2e"
# (minuto, istanza, ticket, ruolo, fase, costo, durata in ms o None se non misurata, TTFT in ms)
CALLS = [
    (0, "T-0001-a1-plan", "T-0001", "design-director", "director-plan", 0.40, 21000, 9000),
    (2, "T-0002-a1", "T-0002", "direction-a", "explorer", 0.90, 9000, 2100),
    (2, "T-0003-a1", "T-0003", "direction-b", "explorer", 0.80, 8600, 1900),
    (6, "T-0002-a1", "T-0002", "direction-a", "explorer", 1.10, 9800, 2300),
    (7, "T-0003-a1", "T-0003", "direction-b", "explorer", 0.70, None, None),
    (12, "T-0001-a1-select", "T-0001", "design-director", "director-select", 0.30, 4600, 2600),
    (15, "T-0004-a1", "T-0004", "identity-designer", "proposer", 1.60, 11000, 3200),
    (24, "T-0001-a1-present", "T-0001", "design-director", "director-present", 0.20, 8200, 2900),
    (31, "T-0005-a1", "T-0005", "identity-designer", "finisher", 2.40, 9400, 2600),
    (44, "T-0005-a1", "T-0005", "identity-designer", "finisher", 2.10, 9100, 2500),
]
TICKETS = [
    ("Consegna officina-e2e", TicketType.DELIVERY, "design-director", ""),
    ("Esplorazione a", TicketType.SKETCH, "direction-a", "explorer"),
    ("Esplorazione b", TicketType.SKETCH, "direction-b", "explorer"),
    ("Proposta X r1", TicketType.PROPOSAL, "identity-designer", "proposer"),
    ("Rifinitura X", TicketType.PRODUCTION, "identity-designer", "finisher"),
]


def at(minute: int) -> str:
    return f"2026-11-02T10:{minute:02d}:00+00:00"


def build(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    ledger = Ledger(folder / "ledger.sqlite")
    ledger.set_project(PROJECT, 20.0, "", "high")
    for title, kind, assignee, prompt in TICKETS:
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
        ledger.open(spec, PROJECT)
    for number, (minute, instance, ticket, role, phase, cost, duration, ttft) in enumerate(CALLS, start=1):
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
                cache_read_tokens=3600,
                cache_write_5m_tokens=200,
                cost_usd=cost,
                stop_reason="tool_use",
                request_id=f"req_e2e_{number}",
                phase=phase if duration is not None else None,
                effort="high" if duration is not None else None,
                duration_ms=duration,
                ttft_ms=ttft,
                reasoning_tokens=60 if duration is not None else None,
            )
        )
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
