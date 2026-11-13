"""The stored and wire values (docs/audit/PLAN.md, Task 1.17): a safety net for Phase 3 and for Task 6.7.

The identifiers are English and their values are Italian words. The values live in ledger rows, transcripts,
operations and the projection, go to the model in tool schemas, and reach the web as OpenAPI enums. They look
like translation candidates and are not (CMT-008).
"""

from __future__ import annotations

import json
from enum import StrEnum

import pytest

from agency.config import REPO_ROOT
from agency.contracts.concept import ConceptStatus
from agency.contracts.judgment import Level
from agency.contracts.outcome import OutcomeState
from agency.contracts.run import RunCommand
from agency.contracts.ticket import Action, Medium, Status, TicketType, Verdict
from agency.insights.compare import Compared
from agency.insights.domain import Lifecycle
from agency.insights.replay import Alignment

RULE = "a stored or wire value changes only through a migration, never a rename"
VALUES: dict[type[StrEnum], set[str]] = {
    TicketType: {
        "produzione",
        "consulenza",
        "revisione",
        "ricerca",
        "qa",
        "consegna",
        "disaccordo",
        "idea",
        "schizzo",
        "proposta",
    },
    ConceptStatus: {"idea", "schizzo", "selezionata", "in-sviluppo", "proposta", "scelta"},
    Medium: {"vettoriale", "motion", "immagine", "interfaccia", "3d", "nessuno"},
    Verdict: {"READY", "REVISE", "NOT_VERIFIED"},
    Status: {"open", "delivered", "accepted", "rework", "blocked", "cancelled"},
    Action: {"deliver", "accept", "rework", "block", "resume", "cancel"},
    Level: {"ordinario", "buono", "eccellente"},
    RunCommand: {"run", "resume", "decide"},
    OutcomeState: {
        "delivered",
        "handed_off",
        "selected",
        "no_concept",
        "presented",
        "concept_rejected",
        "blocked",
    },
    # The three enums of schemas/openapi.json.
    Compared: {"entrambe", "manca prima", "manca dopo", "nessuna"},
    Alignment: {"per richiesta", "per ordine", "nessuna"},
    Lifecycle: {"open", "deliver", "accept", "rework", "block", "resume", "cancel"},
}
WIRE = (Compared, Alignment, Lifecycle)


@pytest.mark.parametrize("vocabulary", list(VALUES), ids=lambda vocabulary: vocabulary.__name__)
def test_stored_and_wire_values_are_fixed(vocabulary: type[StrEnum]) -> None:
    assert {member.value for member in vocabulary} == VALUES[vocabulary], RULE


def test_the_openapi_contract_carries_the_same_values() -> None:
    contract = json.loads((REPO_ROOT / "schemas/openapi.json").read_text(encoding="utf-8"))
    schemas = contract["components"]["schemas"]
    for vocabulary in WIRE:
        assert set(schemas[vocabulary.__name__]["enum"]) == VALUES[vocabulary], RULE
