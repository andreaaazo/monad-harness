"""The ledger's contract with the engine: what it refuses and, from ADR-0058, the ports and entries the
engine reaches it through. `agency.ledger` implements it on SQLite."""

from __future__ import annotations

from collections.abc import Iterable
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


class EvidenceEntry(_Entry):
    """A proof on an exact version of a file. The harness signs it."""

    seq: int | None = None
    at: str
    project: str
    file: str
    sha256: str
    check_name: str
    result: str
    signer: str
    ticket_id: str = ""
    proof: str = ""
    note: str = ""
    inputs_json: str = "{}"


class DerivationEntry(_Entry):
    """An export, and the exact version of the master it was derived from."""

    seq: int | None = None
    at: str
    project: str
    master: str
    master_sha: str
    export: str
    export_sha: str
    how: str = ""


class Proofs(Protocol):
    """The proofs on the files: signed evidence, rendered proofs, and the masters exports come from."""

    def add_evidence(
        self, entry: EvidenceEntry, operation: tuple[str, str, str, str] | None = None
    ) -> None: ...

    def evidence(self, project: str) -> list[EvidenceEntry]: ...

    def add_render(self, project: str, source: str, source_sha: str, proofs: Iterable[str]) -> None: ...

    def renders_of(self, project: str, source: str, source_sha: str) -> list[str]: ...

    def add_derivation(self, link: DerivationEntry) -> None: ...

    def derivations(self, project: str, export: str) -> list[DerivationEntry]: ...
