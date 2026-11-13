"""An instance's outcome: how its work closed. The graph decides the next step from it."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class OutcomeState(StrEnum):
    """Set by the closing tool the instance called, or `blocked` when the ticket was blocked."""

    DELIVERED = "delivered"
    HANDED_OFF = "handed_off"
    SELECTED = "selected"
    NO_CONCEPT = "no_concept"
    PRESENTED = "presented"
    CONCEPT_REJECTED = "concept_rejected"
    BLOCKED = "blocked"


class Outcome(BaseModel):
    """`note` is the closing text. For selection and presentation it is the JSON of the tool's arguments.

    On disk, in the transcripts, it stays `{"state": ..., "note": ...}`: the shape it always had.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: OutcomeState
    note: str = ""
