"""The tables as the code sees them. The schema comes from the migrations: a test checks that they match."""

from __future__ import annotations

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from agency.contracts.concept import ConceptStatus


class ProjectRow(SQLModel, table=True):
    """The client's choices for a project: they still hold after an interruption."""

    __tablename__ = "projects"  # type: ignore[assignment]

    name: str = Field(primary_key=True)
    budget_usd: float
    model: str = ""
    effort: str = ""


class TicketRow(SQLModel, table=True):
    """A ticket: its contract as opened (`spec_json`, `inputs_json`) and its current state, which the chain
    binds (ADR-0047, ADR-0049)."""

    __tablename__ = "tickets"  # type: ignore[assignment]

    id: str = Field(primary_key=True)
    project: str = Field(default="default", index=True)
    spec_json: str
    status: str = Field(index=True)
    verdict: str | None = None
    delivered_json: str = "{}"
    inputs_json: str = "{}"
    created_at: str


class EventRow(SQLModel, table=True):
    """One link of the hash chain: an action on a ticket, or a row written outside any ticket (`-`)."""

    __tablename__ = "events"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(index=True)
    at: str
    actor: str
    action: str
    note: str = ""
    prev_hash: str
    hash: str
    # Version 1 binds no ticket state; version 2 binds the state the event leaves, in `payload_json`
    # (ADR-0047).
    version: int = 1
    payload_json: str = ""


class UsageRow(SQLModel, table=True):
    """A model call: the source of the costs, independent of the telemetry."""

    __tablename__ = "usage"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    ticket_id: str = Field(index=True)
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
    # From M1.6. Empty means not measured: earlier rows stay that way, and do not count as zero.
    run: int | None = Field(default=None, index=True)  # no foreign key: a paid call is always recorded
    phase: str | None = None
    effort: str | None = None
    duration_ms: int | None = None
    ttft_ms: int | None = None
    reasoning_tokens: int | None = None


class EvidenceRow(SQLModel, table=True):
    """A proof on an exact version of a file. The harness signs it."""

    __tablename__ = "evidence"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    file: str = Field(index=True)
    sha256: str
    check_name: str = Field(index=True)
    result: str
    signer: str
    ticket_id: str = ""
    proof: str = ""
    note: str = ""
    inputs_json: str = "{}"


class RenderRow(SQLModel, table=True):
    """A proof rendered from one version of a source file, found again by the source's sha256."""

    __tablename__ = "renders"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    source: str = Field(index=True)
    source_sha: str
    proof: str


class DerivationRow(SQLModel, table=True):
    """An export, and the exact version of the master it was derived from."""

    __tablename__ = "derivations"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    master: str
    master_sha: str
    export: str = Field(index=True)
    export_sha: str
    how: str = ""


class ConceptRow(SQLModel, table=True):
    """An explored idea: the anonymous letter lives here, not on the boards."""

    __tablename__ = "concepts"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    project: str = Field(index=True)
    round: int
    letter: str
    lever: str
    anon: str = ""
    card_json: str = "{}"
    idea_ticket: str
    sketch_ticket: str = ""
    sketch_file: str = ""
    status: str = ConceptStatus.IDEA


class GateRow(SQLModel, table=True):
    """A client decision: the exact words, and the version of the files it was made on."""

    __tablename__ = "gates"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    gate: str
    approved: bool
    choice: str = ""
    text: str = ""
    files_json: str = "{}"


class OperationRow(SQLModel, table=True):
    """A tool's result: on resume, a finished operation does not run again."""

    __tablename__ = "operations"  # type: ignore[assignment]

    id: str = Field(primary_key=True)
    instance: str = Field(index=True)
    tool: str
    result_json: str
    at: str


class RunRow(SQLModel, table=True):
    """A graph run, with the fingerprint of what decides its behaviour. Append-only."""

    __tablename__ = "runs"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    command: str
    digest: str
    fingerprint_json: str


class JudgmentRow(SQLModel, table=True):
    """A person's vote on an exact version of a file, without knowing where it came from. Append-only."""

    __tablename__ = "judgments"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    comparison: str = Field(index=True)
    judge: str
    letter: str
    project: str = Field(index=True)
    file: str
    sha256: str
    level: str
    specific: bool
    best: bool
    why: str


class ArtifactRow(SQLModel, table=True):
    """A kept version: of which file, for which ticket and run, and why. Append-only.

    The content is in the store under its sha256. The same version of the same file for the same reason is
    recorded only once: a resume repeats the step, the registry does not.
    """

    __tablename__ = "artifacts"  # type: ignore[assignment]
    __table_args__ = (
        Index("ux_artifacts_kept", "sha256", "project", "path", "ticket_id", "origin", unique=True),
    )

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    sha256: str  # the unique index starts with it, which is enough to search by hash
    project: str = Field(index=True)
    path: str
    ticket_id: str
    origin: str
    run: int | None = None
    media_type: str
    size: int
