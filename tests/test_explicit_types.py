"""Gate, decisioni ed esiti hanno tipi propri, non dict né stringhe libere (M1.6, punto 8; ADR-0021)."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest
from pydantic import ValidationError

from agency.agents.transcript import Transcript
from agency.artifacts import FileStore
from agency.contracts.gate import GATE, ConceptGate, Decision, FinalGate, GateKind
from agency.contracts.outcome import Outcome, OutcomeState
from agency.ledger import Ledger
from agency.runtime import Session
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import Sandbox
from agency.tools.surface import TOOLS, Toolbox, ToolContext

# I payload come li ha sempre scritti il grafo: un checkpoint in pausa deve ancora leggersi.
CONCEPT_PAYLOAD = {
    "gate": "concept",
    "ticket": "T-0001",
    "files": ["presentation/r1/presentazione.pdf"],
    "options": ["X", "Y"],
    "recommended": "X",
    "reasons": "Regge meglio",
}
FINAL_PAYLOAD = {"gate": "final", "ticket": "T-0001", "files": ["exports/segno.svg"]}


def test_gates_written_before_the_types_still_read() -> None:
    concept = GATE.validate_python(CONCEPT_PAYLOAD)
    assert isinstance(concept, ConceptGate)
    assert (concept.gate, concept.options, concept.recommended) == (GateKind.CONCEPT, ["X", "Y"], "X")
    final = GATE.validate_python(FINAL_PAYLOAD)
    assert isinstance(final, FinalGate) and final.files == ["exports/segno.svg"]


def test_a_gate_is_written_exactly_as_before() -> None:
    assert GATE.dump_python(GATE.validate_python(CONCEPT_PAYLOAD), mode="json") == CONCEPT_PAYLOAD
    assert GATE.dump_python(GATE.validate_python(FINAL_PAYLOAD), mode="json") == FINAL_PAYLOAD


@pytest.mark.parametrize(
    "payload",
    [
        {"gate": "intermedio", "ticket": "T-0001", "files": []},
        CONCEPT_PAYLOAD | {"options": []},  # senza proposte non c'è scelta
        FINAL_PAYLOAD | {"options": ["X"]},
    ],
)
def test_a_gate_that_is_not_one_of_ours_is_refused(payload: dict) -> None:
    with pytest.raises(ValidationError):
        GATE.validate_python(payload)


def test_decision_is_what_the_client_said() -> None:
    decision = Decision(approved=True, text="Mi piace la X", choice="X")
    assert decision.model_dump() == {"approved": True, "text": "Mi piace la X", "choice": "X"}
    assert Decision(approved=False, text="Troppo freddo").choice == ""
    with pytest.raises(ValidationError):  # una stringa non diventa un sì: la decisione arriva solo dal codice
        Decision.model_validate({"approved": "true", "text": ""})


def test_outcome_on_disk_keeps_its_old_shape(tmp_path: Path) -> None:
    transcript = Transcript(tmp_path / "i.jsonl")
    transcript.finish(Outcome(state=OutcomeState.PRESENTED, note="{}"))
    assert (tmp_path / "i.jsonl").read_text(
        encoding="utf-8"
    ) == '{"outcome": {"state": "presented", "note": "{}"}}\n'
    assert transcript.outcome() == Outcome(state=OutcomeState.PRESENTED, note="{}")


@pytest.mark.parametrize("state", ["delivered", "handed_off", "blocked", "selected", "presented"])
def test_outcomes_of_past_projects_still_read(tmp_path: Path, state: str) -> None:
    """Gli stati che compaiono nelle trascrizioni di merlo, merlo2 e merlo3."""
    path = tmp_path / "i.jsonl"
    path.write_text(f'{{"outcome": {{"state": "{state}", "note": "fatto"}}}}\n', encoding="utf-8")
    assert Transcript(path).outcome() == Outcome(state=OutcomeState(state), note="fatto")


def test_an_unknown_outcome_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "i.jsonl"
    path.write_text('{"outcome": {"state": "forse", "note": ""}}\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        Transcript(path).outcome()


@pytest.mark.parametrize("owner", [ToolContext, Session])
def test_no_untyped_bag_is_left(owner: type) -> None:
    loose = [field.name for field in fields(owner) if "Any" in str(field.type) or str(field.type) == "object"]
    assert loose == []


RESUMED = "ripreso dopo un'interruzione"
PROPOSAL = {"letter": "X", "title": "Ruota", "idea": "i", "why": "w", "risk": "r"}
PRESENTED = json.dumps({"proposals": [PROPOSAL], "recommended": "X", "reasons": "regge"})


@pytest.mark.parametrize(
    ("tool", "stored", "state", "note"),
    [
        ("deliver", '{"ok": true}', OutcomeState.DELIVERED, RESUMED),
        ("submit_concept", '{"ok": true}', OutcomeState.DELIVERED, RESUMED),
        ("block", '{"ok": true}', OutcomeState.BLOCKED, RESUMED),
        ("hand_off", '{"ok": true}', OutcomeState.HANDED_OFF, RESUMED),
        ("plan_exploration", '{"ok": true}', OutcomeState.HANDED_OFF, RESUMED),
        ("reject_concept", '{"ok": true}', OutcomeState.CONCEPT_REJECTED, RESUMED),
        ("select_concepts", '{"chosen": ["X"], "reasons": "r"}', OutcomeState.SELECTED, None),
        ("select_concepts", '{"chosen": [], "reasons": "r"}', OutcomeState.NO_CONCEPT, None),
        (
            "draft_presentation",
            '{"proposals": [], "recommended": null, "reasons": "r"}',
            OutcomeState.NO_CONCEPT,
            None,
        ),
        ("present_concepts", PRESENTED, OutcomeState.PRESENTED, None),
        (
            "present_concepts",
            '{"proposals": [], "recommended": null, "reasons": "r"}',
            OutcomeState.NO_CONCEPT,
            None,
        ),
    ],
)
def test_a_closing_tool_already_run_closes_again_on_resume(
    tmp_path: Path, tool: str, stored: str, state: OutcomeState, note: str | None
) -> None:
    """La ripresa non riesegue l'effetto: rilegge l'esito registrato e chiude allo stesso modo."""
    ledger = Ledger(tmp_path / "l.sqlite")
    context = ToolContext(
        "design-director",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "a"),
    )
    ledger.record_operation("i:t1", "i", tool, stored)
    result = Toolbox(context, [TOOLS[tool]]).call("t1", tool, {})
    assert result["content"] == stored and not result.get("is_error")
    assert context.finished == Outcome(state=state, note=stored if note is None else note)


def test_a_draft_with_pages_does_not_close_on_resume(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    context = ToolContext(
        "design-director",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "a"),
    )
    ledger.record_operation("i:t1", "i", "draft_presentation", '{"pagine": ["p1.png"], "poi": "guarda"}')
    Toolbox(context, [TOOLS["draft_presentation"]]).call("t1", "draft_presentation", {})
    assert context.finished is None
