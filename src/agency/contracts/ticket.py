"""Work tickets: status and verdict kept apart, transitions declared as data."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# TicketType, Medium and Verdict are part of the `open_ticket` and `deliver` tool schemas, so they take no
# class docstring. Their values are stored and model-facing: they stay as they are (docs/03-DATA-MODEL.md,
# "Vocabolario").
class TicketType(StrEnum):
    PRODUCTION = "produzione"
    CONSULTATION = "consulenza"
    REVIEW = "revisione"
    RESEARCH = "ricerca"
    QA = "qa"
    DELIVERY = "consegna"
    DISPUTE = "disaccordo"
    IDEA = "idea"  # only to read past projects: since ADR-0014 no ticket of this type is created
    SKETCH = "schizzo"
    PROPOSAL = "proposta"


class Status(StrEnum):
    """A ticket's lifecycle state; `TRANSITIONS` says how it moves."""

    OPEN = "open"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    REWORK = "rework"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


# The statuses in which the assignee still works on a ticket: it can deliver or block it from there.
RUNNABLE: frozenset[Status] = frozenset({Status.OPEN, Status.REWORK})


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
    """What a party does to a ticket; each one is a row of `TRANSITIONS`."""

    DELIVER = "deliver"
    ACCEPT = "accept"
    REWORK = "rework"
    BLOCK = "block"
    RESUME = "resume"
    CANCEL = "cancel"


Party = Literal["sender", "assignee", "either"]

# Who can do what, and from which state: the only definition of the lifecycle.
TRANSITIONS: dict[Action, tuple[frozenset[Status], Status, Party]] = {
    Action.DELIVER: (RUNNABLE, Status.DELIVERED, "assignee"),
    Action.ACCEPT: (frozenset({Status.DELIVERED}), Status.ACCEPTED, "sender"),
    Action.REWORK: (frozenset({Status.DELIVERED, Status.ACCEPTED}), Status.REWORK, "sender"),
    Action.BLOCK: (RUNNABLE, Status.BLOCKED, "either"),
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


class TicketSpec(BaseModel):
    """The handoff contract, as the sender opens it."""

    title: str = Field(min_length=3)
    request: str = Field(min_length=1)
    type: TicketType
    sender: str
    assignee: str
    outputs: list[str] = Field(default_factory=list)
    checks: dict[str, list[str]] = Field(default_factory=dict, description="output pattern → required checks")
    exempt: dict[str, str] = Field(default_factory=dict, description="output → reason for the exemption")
    no_master: dict[str, str] = Field(
        default_factory=dict, description="outputs that legitimately do not derive from the master → reason"
    )
    inputs: list[str] = Field(default_factory=list)
    acceptance: str = ""
    media: list[Medium] = Field(default_factory=list)
    medium_why: str | None = None
    parent: str | None = None
    workspace: str = Field(default="", description="Project subfolder: it is all the ticket sees")
    prompt: str = Field(default="", description="The ticket's own prompt; empty = the role's")
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
