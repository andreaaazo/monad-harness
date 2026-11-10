"""Le regole della proiezione delle chiamate. Pure: niente file, niente database, niente orologio.

Una chiamata registrata da M1.6 in poi porta con sé fase, effort, durata, TTFT e ragionamento. Le chiamate
precedenti no: la fase si ricava con la regola del motore, le misure dalle tracce dell'SDK con `request_id`.
Le misure di una chiamata vengono tutte dalla stessa fonte, mai metà e metà.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agency.contracts import phase


class Measures(StrEnum):
    """Da dove vengono effort, durata, TTFT e ragionamento di una chiamata."""

    REGISTRY = "registro"
    TRACES = "tracce"
    MISSING = "nessuna"


class PhaseSource(StrEnum):
    RECORDED = "registrata"
    DERIVED = "ricavata"


class UsageRecord(BaseModel):
    """Una riga di `usage` com'è nel registro. I campi annullabili sono vuoti sulle righe prima di M1.6."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    ticket_id: str
    role: str
    instance: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    cost_usd: float
    stop_reason: str
    request_id: str
    run: int | None
    phase: str | None
    effort: str | None
    duration_ms: int | None
    ttft_ms: int | None
    reasoning_tokens: int | None


class ProjectRecord(BaseModel):
    """Le scelte del cliente per un progetto. I progetti prima di M1.5 non le hanno."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    budget_usd: float
    model: str
    effort: str


class TicketRecord(BaseModel):
    """Ciò che serve di un ticket per leggere le sue chiamate e il suo stato."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    project: str
    type: str
    assignee: str
    prompt: str
    title: str
    status: str
    verdict: str | None
    created_at: str


class GateRecord(BaseModel):
    """Una decisione del cliente a un gate. Le sue parole restano nel registro: qui servono quando e cosa."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    gate: str
    approved: bool
    choice: str


class ConceptRecord(BaseModel):
    """Un'idea esplorata, con la sua lettera anonima e la frase della scheda."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    project: str
    round: int
    letter: str
    anon: str
    lever: str
    status: str
    concept: str


class JudgmentRecord(BaseModel):
    """Il voto su un file di un confronto alla cieca. `compared` dice quanti file aveva il confronto."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
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
    compared: int


class Lifecycle(StrEnum):
    """What the registry writes into a ticket's history, proofs aside: the opening and the transitions of
    `Action`. A test keeps the two aligned."""

    OPEN = "open"
    DELIVER = "deliver"
    ACCEPT = "accept"
    REWORK = "rework"
    BLOCK = "block"
    RESUME = "resume"
    CANCEL = "cancel"


# I passi indietro: un ticket rimandato, bloccato o annullato.
SETBACKS = frozenset({Lifecycle.REWORK, Lifecycle.BLOCK, Lifecycle.CANCEL})


class EventRecord(BaseModel):
    """Un passo nella storia di un ticket: chi, cosa e quando. `reason` è la nota di chi lo ha fatto, solo per
    un passo indietro; le parole delle altre note restano nel registro."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    ticket_id: str
    actor: str
    action: Lifecycle
    reason: str | None


class CheckRecord(BaseModel):
    """Una prova su un file: quale controllo, con che esito, chi la firma e perché. FAIL è l'unico esito che
    boccia: PASS, NOT_APPLICABLE e MEASURED no (qa/evidence.py)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    ticket_id: str
    file: str
    check_name: str
    result: str
    signer: str
    reason: str


class ToolCallRecord(BaseModel):
    """Una chiamata a uno strumento in una trascrizione. `refusal`: il testo dello strumento quando ha detto
    no, accorciato; vuoto se ha risposto. `turn` conta le risposte del modello nell'istanza, da 1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    project: str
    instance: str
    turn: int
    tool: str
    refusal: str | None


class ImageRef(BaseModel):
    """An image returned to an instance: its position in the transcript, from 0, its media type, and whether
    the dashboard serves it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    media_type: str
    servable: bool


class ToolExchange(BaseModel):
    """Uno strumento chiesto dal modello e la sua risposta. `answered` è falso se la risposta non c'è: il
    lavoro si è fermato prima."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    input: str
    answered: bool
    refused: bool
    result: str
    images: list[ImageRef]


class AssistantTurn(BaseModel):
    """Una risposta del modello in trascrizione. `request_id` c'è dalle trascrizioni di M1.6 in poi; `notes`
    sono i messaggi dell'harness che la seguono, come un promemoria."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str | None
    thinking: list[str]
    hidden_thinking: int
    text: list[str]
    tools: list[ToolExchange]
    notes: list[str]


class TranscriptRecord(BaseModel):
    """La trascrizione di un'istanza, letta quando la si apre: non entra nella proiezione (ADR-0038)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: str
    instance: str
    task: str
    turns: list[AssistantTurn]
    outcome_state: str | None
    outcome_note: str
    images: int
    unreadable: int


class TranscriptImage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    media_type: str
    data: bytes


class RunRecord(BaseModel):
    """Un'esecuzione del grafo, con l'impronta di ciò che ne decide il comportamento (ADR-0026). L'impronta
    resta il JSON del registro: la legge `agency.contracts.run`, e un'impronta di una forma che questa
    versione non conosce non rompe la proiezione."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    command: str
    digest: str
    fingerprint_json: str


class TraceMeasure(BaseModel):
    """Le misure che l'SDK scrive nella traccia di una richiesta."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str
    duration_ms: int | None
    ttft_ms: int | None
    effort: str | None
    reasoning_tokens: int | None


class Call(BaseModel):
    """Una chiamata nella proiezione: le colonne della tabella `calls` nascono da qui."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    run: int | None
    ticket_id: str
    ticket_type: str
    role: str
    instance: str
    phase: str
    phase_source: PhaseSource
    model: str
    effort: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    cost_usd: float
    stop_reason: str
    request_id: str
    duration_ms: int | None
    ttft_ms: int | None
    reasoning_tokens: int | None
    measures: Measures


def derive_phase(usage: UsageRecord, tickets: Mapping[str, TicketRecord]) -> str:
    """La fase come l'avrebbe registrata il motore: un ticket che il registro non ha lascia il ruolo."""
    ticket = tickets.get(usage.ticket_id)
    return phase.of(usage.role, ticket.prompt if ticket else "", phase.mode_of(usage.instance))


def _measures(usage: UsageRecord, trace: TraceMeasure | None) -> tuple[Measures, TraceMeasure | None]:
    """La durata c'è su ogni chiamata registrata da M1.6: è lei a dire se la riga si misura da sola."""
    if usage.duration_ms is not None:
        own = TraceMeasure(
            request_id=usage.request_id,
            duration_ms=usage.duration_ms,
            ttft_ms=usage.ttft_ms,
            effort=usage.effort,
            reasoning_tokens=usage.reasoning_tokens,
        )
        return Measures.REGISTRY, own
    if trace is not None:
        return Measures.TRACES, trace
    return Measures.MISSING, None


def project_calls(
    usages: list[UsageRecord], tickets: Mapping[str, TicketRecord], traces: Mapping[str, TraceMeasure]
) -> list[Call]:
    calls = []
    for usage in usages:
        source, measured = _measures(usage, traces.get(usage.request_id))
        ticket = tickets.get(usage.ticket_id)
        recorded = usage.phase is not None
        calls.append(
            Call(
                seq=usage.seq,
                at=usage.at,
                project=usage.project,
                run=usage.run,
                ticket_id=usage.ticket_id,
                ticket_type=ticket.type if ticket else "",
                role=usage.role,
                instance=usage.instance,
                phase=usage.phase if usage.phase is not None else derive_phase(usage, tickets),
                phase_source=PhaseSource.RECORDED if recorded else PhaseSource.DERIVED,
                model=usage.model,
                effort=measured.effort if measured else None,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_5m_tokens=usage.cache_write_5m_tokens,
                cache_write_1h_tokens=usage.cache_write_1h_tokens,
                cost_usd=usage.cost_usd,
                stop_reason=usage.stop_reason,
                request_id=usage.request_id,
                duration_ms=measured.duration_ms if measured else None,
                ttft_ms=measured.ttft_ms if measured else None,
                reasoning_tokens=measured.reasoning_tokens if measured else None,
                measures=source,
            )
        )
    return calls


class Projected(BaseModel):
    """Tutto ciò che entra nella proiezione, in una volta sola."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calls: list[Call]
    projects: list[ProjectRecord]
    tickets: list[TicketRecord]
    gates: list[GateRecord]
    concepts: list[ConceptRecord]
    judgments: list[JudgmentRecord]
    events: list[EventRecord]
    checks: list[CheckRecord]
    tool_calls: list[ToolCallRecord]
    runs: list[RunRecord]


class SourceStamp(BaseModel):
    """A file the projection is built from, as it was when read. If the file is missing, the size is empty."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    size: int | None
    modified_ns: int | None


class Provenance(BaseModel):
    """What the projection was built from: a reader knows when, from which registry, and how complete it
    is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    built_at: str
    sources: list[SourceStamp]
    registry_revision: str
    calls: int
    from_registry: int
    from_traces: int
    unmeasured: int
    phases_recorded: int
    phases_derived: int
    unreadable_trace_lines: int
    unreadable_transcript_lines: int


def provenance(
    calls: list[Call],
    *,
    built_at: str,
    sources: list[SourceStamp],
    revision: str,
    unreadable: int,
    unreadable_transcripts: int,
) -> Provenance:
    def count(source: Measures) -> int:
        return sum(1 for call in calls if call.measures is source)

    recorded = sum(1 for call in calls if call.phase_source is PhaseSource.RECORDED)
    return Provenance(
        built_at=built_at,
        sources=sources,
        registry_revision=revision,
        calls=len(calls),
        from_registry=count(Measures.REGISTRY),
        from_traces=count(Measures.TRACES),
        unmeasured=count(Measures.MISSING),
        phases_recorded=recorded,
        phases_derived=len(calls) - recorded,
        unreadable_trace_lines=unreadable,
        unreadable_transcript_lines=unreadable_transcripts,
    )
