"""L'esito di un'istanza: come si è chiuso il suo lavoro. Il grafo decide il passo successivo da qui."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class OutcomeState(StrEnum):
    DELIVERED = "delivered"
    HANDED_OFF = "handed_off"
    SELECTED = "selected"
    NO_CONCEPT = "no_concept"
    PRESENTED = "presented"
    CONCEPT_REJECTED = "concept_rejected"
    BLOCKED = "blocked"


class Outcome(BaseModel):
    """`note` è il testo di chiusura. Per selezione e presentazione è il JSON degli argomenti dello strumento.

    Su disco, nelle trascrizioni, resta `{"state": ..., "note": ...}`: la forma di sempre.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: OutcomeState
    note: str = ""
