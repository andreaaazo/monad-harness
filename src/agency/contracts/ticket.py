"""Ticket di lavoro: stato e verdetto separati, transizioni dichiarate come dati."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TicketType(StrEnum):
    PRODUCTION = "produzione"
    CONSULTATION = "consulenza"
    REVIEW = "revisione"
    RESEARCH = "ricerca"
    QA = "qa"
    DELIVERY = "consegna"
    DISPUTE = "disaccordo"
    IDEA = "idea"  # solo per leggere i progetti passati: dopo ADR-0014 non si crea più
    SKETCH = "schizzo"
    PROPOSAL = "proposta"


class Status(StrEnum):
    OPEN = "open"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    REWORK = "rework"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class Verdict(StrEnum):
    READY = "READY"
    REVISE = "REVISE"
    NOT_VERIFIED = "NOT_VERIFIED"


class Medium(StrEnum):
    VECTOR = "vettoriale"
    MOTION = "motion"
    IMAGE = "immagine"
    INTERFACE = "interfaccia"
    THREE_D = "3d"
    NONE = "nessuno"


class Action(StrEnum):
    DELIVER = "deliver"
    ACCEPT = "accept"
    REWORK = "rework"
    BLOCK = "block"
    RESUME = "resume"
    CANCEL = "cancel"


Party = Literal["sender", "assignee", "either"]

# Chi può fare cosa, e da quale stato: l'unica definizione del ciclo di vita.
TRANSITIONS: dict[Action, tuple[frozenset[Status], Status, Party]] = {
    Action.DELIVER: (frozenset({Status.OPEN, Status.REWORK}), Status.DELIVERED, "assignee"),
    Action.ACCEPT: (frozenset({Status.DELIVERED}), Status.ACCEPTED, "sender"),
    Action.REWORK: (frozenset({Status.DELIVERED, Status.ACCEPTED}), Status.REWORK, "sender"),
    Action.BLOCK: (frozenset({Status.OPEN, Status.REWORK}), Status.BLOCKED, "either"),
    Action.RESUME: (frozenset({Status.BLOCKED}), Status.OPEN, "either"),
    Action.CANCEL: (
        frozenset({Status.OPEN, Status.DELIVERED, Status.REWORK, Status.BLOCKED}),
        Status.CANCELLED,
        "sender",
    ),
}

NO_CHECK_TYPES = frozenset(
    {TicketType.CONSULTATION, TicketType.RESEARCH, TicketType.DISPUTE, TicketType.IDEA}
)
AUTHOR_TYPES = frozenset({TicketType.PRODUCTION, TicketType.SKETCH, TicketType.PROPOSAL})
REVIEW_TYPES = frozenset({TicketType.QA, TicketType.REVIEW})
REVIEWERS = frozenset({"qa-inspector", "critic", "legal-reviewer"})


class TicketSpec(BaseModel):
    """Il contratto di passaggio, così come lo apre il mittente."""

    title: str = Field(min_length=3)
    request: str = Field(min_length=1)
    type: TicketType
    sender: str
    assignee: str
    outputs: list[str] = Field(default_factory=list)
    checks: dict[str, list[str]] = Field(
        default_factory=dict, description="pattern di output → controlli richiesti"
    )
    exempt: dict[str, str] = Field(default_factory=dict, description="output → motivo dell'esenzione")
    no_master: dict[str, str] = Field(
        default_factory=dict, description="output che legittimamente non derivano dal master → motivo"
    )
    inputs: list[str] = Field(default_factory=list)
    acceptance: str = ""
    media: list[Medium] = Field(default_factory=list)
    medium_why: str | None = None
    parent: str | None = None
    workspace: str = Field(
        default="", description="Sottocartella del progetto: è tutto ciò che il ticket vede"
    )
    prompt: str = Field(default="", description="Prompt specifico del ticket; vuoto = quello del ruolo")
    effort: str | None = None

    @model_validator(mode="after")
    def _contract(self) -> TicketSpec:
        if self.type in AUTHOR_TYPES and not self.media:
            raise ValueError("una produzione dichiara il mezzo")
        if Medium.NONE in self.media and len((self.medium_why or "").strip()) < 10:
            raise ValueError("mezzo 'nessuno' richiede il motivo")
        if self.type is not TicketType.DISPUTE and not self.outputs:
            raise ValueError("dichiara gli output")
        if self.type not in NO_CHECK_TYPES and not self.checks:
            raise ValueError("dichiara i controlli di accettazione")
        for path in (*self.outputs, *self.inputs, *self.checks):
            pure = PurePosixPath(path)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"{path} è fuori dalla cartella del lavoro")
        for output in self.outputs:
            if output.endswith("/"):
                raise ValueError(f"{output} è una cartella: dichiara file o glob")
        for path, why in self.exempt.items():
            if len(why.strip()) < 10:
                raise ValueError(f"esenzione di {path} senza un motivo vero")
        return self
