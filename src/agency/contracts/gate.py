"""I gate del cliente: cosa gli si mostra quando il lavoro si ferma, e cosa risponde.

Il campo `gate` fa da discriminante e ha il nome di sempre: un checkpoint salvato prima di questi tipi si
legge ancora. Nel checkpoint il gate resta un dict semplice (`GATE.dump_python(..., mode="json")`): il tipo
vive nel codice, e il formato salvato non dipende dal serializzatore di LangGraph.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class GateKind(StrEnum):
    CONCEPT = "concept"
    FINAL = "final"


class ConceptGate(BaseModel):
    """Le proposte sviluppate, nel PDF che il cliente riceve, e quella che lo studio raccomanda."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: Literal[GateKind.CONCEPT] = GateKind.CONCEPT
    ticket: str
    files: list[str]
    options: list[str] = Field(min_length=1)
    recommended: str
    reasons: str


class FinalGate(BaseModel):
    """Il lavoro finito: le consegne del ticket principale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: Literal[GateKind.FINAL] = GateKind.FINAL
    ticket: str
    files: list[str]


type Gate = Annotated[ConceptGate | FinalGate, Field(discriminator="gate")]
GATE: TypeAdapter[Gate] = TypeAdapter(Gate)


class Decision(BaseModel):
    """La risposta del cliente a un gate. `choice` è la lettera della proposta, solo al gate `concept`."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    approved: bool
    text: str
    choice: str = ""
