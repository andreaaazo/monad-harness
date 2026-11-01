"""Tabelle SQLite. Il proprietario dello schema è questo modulo; ogni modifica è una migrazione."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class ProjectRow(SQLModel, table=True):
    """Le scelte del cliente per un progetto: restano valide anche dopo un'interruzione."""

    __tablename__ = "projects"  # type: ignore[assignment]

    name: str = Field(primary_key=True)
    budget_usd: float
    model: str = ""
    effort: str = ""


class TicketRow(SQLModel, table=True):
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
    __tablename__ = "events"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(index=True)
    at: str
    actor: str
    action: str
    note: str = ""
    prev_hash: str
    hash: str


class UsageRow(SQLModel, table=True):
    """Una chiamata al modello: la fonte dei costi, indipendente dalla telemetria."""

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


class EvidenceRow(SQLModel, table=True):
    """Una prova su una versione precisa di un file. La firma la mette l'harness."""

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
    __tablename__ = "renders"  # type: ignore[assignment]

    seq: int | None = Field(default=None, primary_key=True)
    at: str
    project: str = Field(index=True)
    source: str = Field(index=True)
    source_sha: str
    proof: str


class DerivationRow(SQLModel, table=True):
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
    """Un'idea esplorata: la lettera anonima sta qui, non sulle tavole."""

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
    status: str = "idea"


class GateRow(SQLModel, table=True):
    """Una decisione del cliente: parole testuali e versione dei file su cui è stata presa."""

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
    """Esito di uno strumento: alla ripresa un'operazione conclusa non si riesegue."""

    __tablename__ = "operations"  # type: ignore[assignment]

    id: str = Field(primary_key=True)
    instance: str = Field(index=True)
    tool: str
    result_json: str
    at: str
