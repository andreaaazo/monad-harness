"""The prefix of every request, byte for byte: the tools and the system prompt of each phase.

It is what the cache reuses and what the model sees first. A changed byte invalidates the cache and changes
the behaviour, and no other test would notice (ADR-0021). The comparison is on the text: equality between
dicts would ignore the order of the keys, which does change the bytes sent.
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
from agency.workshop.craft import CommandIndex

SNAPSHOTS = Path(__file__).parent / "snapshots" / "requests"
ROLE_PROMPTS = REPO_ROOT / "prompts" / "roles"
UPDATE = "UPDATE_SNAPSHOTS=1 uv run pytest tests/test_request_snapshots.py"


@dataclass(frozen=True)
class Phase:
    """A real phase of the work. Its name is that of the prompt it receives, one per phase."""

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
    """The first request is all that is needed: the work ends there."""


class FirstRequest:
    """Takes the API's place: it keeps the request as it comes from the gateway."""

    def __init__(self) -> None:
        self.params: dict = {}

    def count_tokens(self, params: dict) -> int:
        return 1000

    def stream(self, params: dict) -> dict:
        self.params = params
        raise Stop


def prefix(phase: Phase, tmp_path: Path) -> str:
    settings = Settings(data_dir=tmp_path / "data", projects_dir=tmp_path / "projects", _env_file=None)  # type: ignore[call-arg]
    ledger = Ledger(settings.layout.ledger)
    ledger.set_project("prova", 25.0)  # without a declared cap the request would not go out (ADR-0043)
    transport = FirstRequest()
    runner = AgentRunner(
        ModelGateway(transport, ledger, settings),
        ledger,
        settings,
        CommandIndex([]),
        FileStore(settings.layout.artifacts),
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
    assert snapshot.is_file(), f"no snapshot for {phase.name}. If that is intended: {UPDATE}"
    assert actual == snapshot.read_text(encoding="utf-8"), (
        f"the prefix changed. If that is intended: {UPDATE}"
    )


def test_every_role_prompt_has_a_phase_and_a_snapshot() -> None:
    phases = {phase.name for phase in PHASES}
    assert phases == {path.stem for path in ROLE_PROMPTS.glob("*.md")}
    assert phases == {path.stem for path in SNAPSHOTS.glob("*.json")}
