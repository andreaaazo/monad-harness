"""The ledger's contract with the engine: what it refuses and, from ADR-0058, the ports and entries the
engine reaches it through. `agency.ledger` implements it on SQLite."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from agency.contracts.concept import ConceptStatus
from agency.contracts.judgment import Judged, Judgment
from agency.contracts.run import Fingerprint, RunCommand


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


class ProjectEntry(_Entry):
    """The client's choices for a project: they still hold after an interruption."""

    name: str
    budget_usd: float
    model: str = ""
    effort: str = ""


class TicketEntry(_Entry):
    """A ticket: its contract as opened (`spec_json`, `inputs_json`) and its current state, which the chain
    binds (ADR-0047, ADR-0049)."""

    id: str
    project: str = "default"
    spec_json: str
    status: str
    verdict: str | None = None
    delivered_json: str = "{}"
    inputs_json: str = "{}"
    created_at: str


class EventEntry(_Entry):
    """One link of the hash chain: an action on a ticket, or a row written outside any ticket (`-`)."""

    seq: int | None = None
    ticket_id: str
    at: str
    actor: str
    action: str
    note: str = ""
    prev_hash: str
    hash: str
    version: int = 1
    payload_json: str = ""


class UsageEntry(_Entry):
    """A model call: the source of the costs, independent of the telemetry."""

    seq: int | None = None
    at: str
    project: str
    ticket_id: str
    role: str
    instance: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cost_usd: float = 0.0
    stop_reason: str = ""
    request_id: str = ""
    run: int | None = None
    phase: str | None = None
    effort: str | None = None
    duration_ms: int | None = None
    ttft_ms: int | None = None
    reasoning_tokens: int | None = None


class OperationEntry(_Entry):
    """A tool's result: on resume, a finished operation does not run again."""

    id: str
    instance: str
    tool: str
    result_json: str
    at: str


class RunEntry(_Entry):
    """A graph run, with the fingerprint of what decides its behaviour. Append-only."""

    seq: int | None = None
    at: str
    project: str
    command: str
    digest: str
    fingerprint_json: str


class JudgmentEntry(_Entry):
    """A person's vote on an exact version of a file, without knowing where it came from. Append-only."""

    seq: int | None = None
    at: str
    comparison: str
    judge: str
    letter: str
    project: str
    file: str
    sha256: str
    level: str
    specific: bool
    best: bool
    why: str


class ArtifactEntry(_Entry):
    """A kept version: of which file, for which ticket and run, and why. Append-only.

    The content is in the store under its sha256. The same version of the same file for the same reason is
    recorded only once: a resume repeats the step, the registry does not.
    """

    seq: int | None = None
    at: str
    sha256: str
    project: str
    path: str
    ticket_id: str
    origin: str
    run: int | None = None
    media_type: str
    size: int


class Usage(Protocol):
    """The paid model calls: the source of the costs."""

    def record_usage(self, entry: UsageEntry) -> None: ...

    def spent(self, project: str) -> float: ...

    def usage(self, project: str) -> list[UsageEntry]: ...


class KeptArtifacts(Protocol):
    """The kept versions of the files: which file, for which ticket and run, and why."""

    def record_artifacts(self, entries: list[ArtifactEntry]) -> None: ...

    def artifacts(self, project: str) -> list[ArtifactEntry]: ...

    def artifacts_with(self, prefix: str) -> list[ArtifactEntry]: ...

    def all_artifacts(self) -> list[ArtifactEntry]: ...


class Runs(Protocol):
    """The graph runs with their fingerprints, and the blind judgments of their files."""

    def record_run(self, project: str, command: RunCommand, fingerprint: Fingerprint) -> int: ...

    def runs(self, project: str) -> list[RunEntry]: ...

    def run(self, seq: int) -> RunEntry | None: ...

    def record_judgment(self, comparison: str, judgment: Judgment, files: dict[str, Judged]) -> None: ...

    def judgments(self, project: str) -> list[JudgmentEntry]: ...

    def comparison(self, comparison: str) -> list[JudgmentEntry]: ...
