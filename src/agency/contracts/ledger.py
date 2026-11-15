"""The ledger's contract with the engine: what it refuses and, from ADR-0058, the ports and entries the
engine reaches it through. `agency.ledger` implements it on SQLite."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from agency.contracts.concept import ConceptStatus


class IllegalTransition(Exception):
    """The action is not allowed from the ticket's current status."""


class ForbiddenAction(Exception):
    """The actor has no right to take the action."""


class _Entry(BaseModel):
    """A ledger row as it crosses the boundary: the same fields, immutable, read from the row's attributes."""

    model_config = ConfigDict(frozen=True, from_attributes=True)


class ConceptEntry(_Entry):
    """An explored idea: the anonymous letter lives here, not on the boards."""

    seq: int | None = None
    project: str
    round: int
    letter: str
    lever: str
    anon: str = ""
    card_json: str = "{}"
    idea_ticket: str
    sketch_ticket: str = ""
    sketch_file: str = ""
    status: str = ConceptStatus.IDEA


class GateEntry(_Entry):
    """A client decision: the exact words, and the version of the files it was made on."""

    seq: int | None = None
    at: str
    project: str
    gate: str
    approved: bool
    choice: str = ""
    text: str = ""
    files_json: str = "{}"


class Concepts(Protocol):
    """The explored ideas of a project."""

    def concepts(self, project: str, round_: int | None = None) -> list[ConceptEntry]: ...

    def update_concept(self, idea_ticket: str, **fields: object) -> None: ...


class Gates(Protocol):
    """The client's decisions at the gates."""

    def add_gate(self, gate: GateEntry) -> None: ...

    def gates(self, project: str) -> list[GateEntry]: ...
