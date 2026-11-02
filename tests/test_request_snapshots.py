"""Il prefisso di ogni richiesta, byte per byte: strumenti e system prompt per ogni fase.

È ciò che la cache riusa e ciò che il modello vede per primo. Un byte cambiato invalida la cache e cambia il
comportamento, e nessun altro test se ne accorgerebbe (ADR-0021). Il confronto è sul testo: l'uguaglianza tra
dizionari ignorerebbe l'ordine delle chiavi, che invece cambia i byte inviati.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from agency.agents.loop import AgentRunner
from agency.artifacts import FileStore
from agency.config import REPO_ROOT, Settings
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.gateway import ModelGateway
from agency.ledger import Ledger
from agency.tools.craft import CommandIndex

SNAPSHOTS = Path(__file__).parent / "snapshots" / "requests"
ROLE_PROMPTS = REPO_ROOT / "prompts" / "roles"
UPDATE = "UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py"


@dataclass(frozen=True)
class Phase:
    """Una fase reale del lavoro. Il nome è quello del prompt che riceve, uno per fase."""

    name: str
    assignee: str
    type: TicketType
    prompt: str = ""
    mode: str = ""


PHASES = (
    Phase("director-plan", "design-director", TicketType.DELIVERY, mode="plan"),
    Phase("explorer", "direction-a", TicketType.SKETCH, prompt="explorer"),
    Phase("critic-board", "critic", TicketType.REVIEW, prompt="critic-board"),
    Phase("director-select", "design-director", TicketType.DELIVERY, mode="select"),
    Phase("proposer", "identity-designer", TicketType.PROPOSAL, prompt="proposer"),
    Phase("director-present", "design-director", TicketType.DELIVERY, mode="present"),
    Phase("finisher", "identity-designer", TicketType.PRODUCTION, prompt="finisher"),
    Phase("identity-designer", "identity-designer", TicketType.PRODUCTION),
    Phase("critic", "critic", TicketType.REVIEW),
    Phase("qa-inspector", "qa-inspector", TicketType.QA),
    Phase("design-director", "design-director", TicketType.DELIVERY),
)


class Stop(Exception):
    """La prima richiesta è tutto ciò che serve: il lavoro finisce lì."""


class FirstRequest:
    """Prende il posto dell'API: tiene la richiesta così come arriva dal gateway."""

    def __init__(self) -> None:
        self.params: dict = {}

    def count_tokens(self, params: dict) -> int:
        return 1000

    def stream(self, params: dict) -> dict:
        self.params = params
        raise Stop


def prefix(phase: Phase, tmp_path: Path) -> str:
    settings = Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "projects", _env_file=None)  # type: ignore[call-arg]
    ledger = Ledger(settings.ledger_path)
    transport = FirstRequest()
    runner = AgentRunner(
        ModelGateway(transport, ledger, settings),
        ledger,
        settings,
        CommandIndex([]),
        FileStore(settings.artifacts_dir),
    )
    spec = TicketSpec(
        title="Prova",
        request="Prova",
        type=phase.type,
        sender="design-director",
        assignee=phase.assignee,
        outputs=["segno.svg"],
        checks={"*.svg": ["svg_audit"]},
        media=[Medium.VECTOR],
        prompt=phase.prompt,
    )
    with pytest.raises(Stop):
        runner.run(ledger.open(spec, "prova"), mode=phase.mode)
    fields = {"system": transport.params["system"], "tools": transport.params["tools"]}
    return json.dumps(fields, ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize("phase", PHASES, ids=lambda phase: phase.name)
def test_request_prefix_stays_byte_identical(phase: Phase, tmp_path: Path) -> None:
    actual = prefix(phase, tmp_path)
    snapshot = SNAPSHOTS / f"{phase.name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(actual, encoding="utf-8")
        return
    assert snapshot.is_file(), f"manca lo snapshot di {phase.name}. Se è voluto: {UPDATE}"
    assert actual == snapshot.read_text(encoding="utf-8"), f"prefisso cambiato. Se è voluto: {UPDATE}"


def test_every_role_prompt_has_a_phase_and_a_snapshot() -> None:
    phases = {phase.name for phase in PHASES}
    assert phases == {path.stem for path in ROLE_PROMPTS.glob("*.md")}
    assert phases == {path.stem for path in SNAPSHOTS.glob("*.json")}
