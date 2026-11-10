"""The client's gates: what the client is shown when the work stops, and what they answer.

The `gate` field is the discriminator and keeps the name it always had, so a checkpoint saved before these
types still reads. In the checkpoint the gate stays a plain dict (`GATE.dump_python(..., mode="json")`): the
type lives in the code, and the saved format does not depend on LangGraph's serializer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class GateKind(StrEnum):
    """Where the work waits for the client: the choice among concepts, or the finished work."""

    CONCEPT = "concept"
    FINAL = "final"


class ConceptGate(BaseModel):
    """The developed proposals, in the PDF the client receives, and the one the studio recommends."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: Literal[GateKind.CONCEPT] = GateKind.CONCEPT
    ticket: str
    files: list[str]
    options: list[str] = Field(min_length=1)
    recommended: str
    reasons: str


class FinalGate(BaseModel):
    """The finished work: the deliveries of the main ticket."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: Literal[GateKind.FINAL] = GateKind.FINAL
    ticket: str
    files: list[str]


type Gate = Annotated[ConceptGate | FinalGate, Field(discriminator="gate")]
GATE: TypeAdapter[Gate] = TypeAdapter(Gate)


class Decision(BaseModel):
    """The client's answer to a gate. `choice` is the proposal's letter, only at the `concept` gate."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    approved: bool
    text: str
    choice: str = ""
