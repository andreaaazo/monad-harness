"""The projection's rules, and the records it is made of. Pure: no files, no database, no clock.

A call recorded from M1.6 on carries its phase, effort, duration, TTFT and reasoning. Earlier calls do not:
the phase is derived with the engine's rule, and the measures come from the SDK traces by `request_id`. A
call's measures all come from the same source, never half from each.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agency.contracts import phase


class Measures(StrEnum):
    """Where a call's effort, duration, TTFT and reasoning come from."""

    REGISTRY = "registro"
    TRACES = "tracce"
    MISSING = "nessuna"


class PhaseSource(StrEnum):
    """Whether the engine recorded a call's phase, or it was derived with the engine's rule."""

    RECORDED = "registrata"
    DERIVED = "ricavata"


class UsageRecord(BaseModel):
    """A `usage` row as the registry holds it. The nullable fields are empty on rows from before M1.6."""

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
    """The client's choices for a project. Projects from before M1.5 have none."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    budget_usd: float
    model: str
    effort: str


class TicketRecord(BaseModel):
    """What is needed of a ticket to read its calls and its status."""

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
    """A client decision at a gate. Its words stay in the registry: here only when and what matter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    gate: str
    approved: bool
    choice: str


class ConceptRecord(BaseModel):
    """An explored idea, with its anonymous letter and the sentence of its card."""

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
    """The vote on one file of a blind comparison. `compared` says how many files the comparison had."""

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


# The steps back: work sent back, stopped or dropped. RESUME is not one: it undoes a BLOCK, which counts.
SETBACKS = frozenset({Lifecycle.REWORK, Lifecycle.BLOCK, Lifecycle.CANCEL})


class EventRecord(BaseModel):
    """A step in a ticket's history: who, what and when. `reason` is the note of whoever took it, only
    for a step back; the words of the other notes stay in the registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    ticket_id: str
    actor: str
    action: Lifecycle
    reason: str | None


class CheckRecord(BaseModel):
    """A proof on a file: which check, with what result, who signs it and why. FAIL is the only result
    that fails: PASS, NOT_APPLICABLE and MEASURED do not (qa/evidence.py)."""

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
    """A tool call in a transcript. `refusal`: the tool's text when it said no, shortened; None
    otherwise. `turn` counts the model's answers in the instance, from 1."""

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
    """A tool the model asked for, and its answer. `answered` is false when there is no answer: the
    work stopped first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    input: str
    answered: bool
    refused: bool
    result: str
    images: list[ImageRef]


class AssistantTurn(BaseModel):
    """A model answer in a transcript. `request_id` exists in transcripts from M1.6 on; `notes` are
    the harness messages that follow it, such as a reminder."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str | None
    thinking: list[str]
    hidden_thinking: int
    text: list[str]
    tools: list[ToolExchange]
    notes: list[str]


class TranscriptRecord(BaseModel):
    """An instance's transcript, read when it is opened: it does not enter the projection (ADR-0038)."""

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
    """An image decoded from a transcript, with the media type it is served as."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    media_type: str
    data: bytes


class RunRecord(BaseModel):
    """A graph run, with the fingerprint of what decides its behaviour (ADR-0026). The fingerprint stays
    the registry's JSON: `agency.contracts.run` reads it, and a fingerprint of a shape this version does not
    know does not break the projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at: str
    project: str
    command: str
    digest: str
    fingerprint_json: str


class TraceMeasure(BaseModel):
    """The measures the SDK writes into a request's trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str
    duration_ms: int | None
    ttft_ms: int | None
    effort: str | None
    reasoning_tokens: int | None


class Call(BaseModel):
    """A call in the projection: the columns of the `calls` table come from here."""

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
    """The phase as the engine would have recorded it: a ticket the registry lacks leaves the role."""
    ticket = tickets.get(usage.ticket_id)
    return phase.of(usage.role, ticket.prompt if ticket else "", phase.mode_of(usage.instance))


def _measures(usage: UsageRecord, trace: TraceMeasure | None) -> tuple[Measures, TraceMeasure | None]:
    """The duration is on every call recorded since M1.6: it says whether the row measures itself."""
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
    """One call per usage row, with its phase and with its measures from a single source."""
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
    """Everything that goes into the projection, all at once."""

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
