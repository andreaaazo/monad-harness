"""La vista Strumenti e QA: dove sbaglia, con le parole di chi ha detto no.

Tre fonti dicono di no. I controlli, con le prove del registro: FAIL è l'unico esito che boccia. Gli
strumenti, che rifiutano una richiesta e lo scrivono nella trascrizione. Le persone dello studio, che
rimandano o bloccano un ticket con una nota. Un no non dice di chi è la colpa: un contratto sbagliato e un
lavoro sbagliato si distinguono leggendo il motivo, e il motivo è qui per intero.

Un controllo passa al primo colpo su un file quando la sua prima prova su quel file, in quel ticket, non è
FAIL.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agency.contracts.ticket import Status
from agency.insights import sums
from agency.insights.domain import Call, CheckRecord, ToolCallRecord
from agency.insights.flow import Setback, setbacks, ticket_phase
from agency.insights.ports import ProjectData

FAIL = "FAIL"


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CheckSummary(_View):
    """A check: how many proofs, how many FAILs, on how many files of a ticket, and on how many it passed at
    once."""

    check_name: str
    runs: int
    failed: int
    subjects: int
    first_pass: int


class CheckFailure(_View):
    at: str
    check_name: str
    ticket_id: str
    title: str
    phase: str
    file: str
    signer: str
    reason: str


class ToolSummary(_View):
    tool: str
    uses: int
    refused: int
    instances: int


class Refusal(_View):
    """A tool that said no, at turn `turn` of the instance, in its own words."""

    instance: str
    ticket_id: str
    role: str
    phase: str
    turn: int
    tool: str
    message: str


class QualityReport(_View):
    project: str
    subjects: int
    first_pass: int
    checks: list[CheckSummary]
    failures: list[CheckFailure]
    uses: int
    refused: int
    tools: list[ToolSummary]
    refusals: list[Refusal]
    blocked: int
    setbacks: list[Setback]


def _check(name: str, records: list[CheckRecord]) -> CheckSummary:
    subjects = sums.groups(records, lambda record: f"{record.ticket_id}\n{record.file}")
    return CheckSummary(
        check_name=name,
        runs=len(records),
        failed=sum(1 for record in records if record.result == FAIL),
        subjects=len(subjects),
        first_pass=sum(1 for group in subjects.values() if group[0].result != FAIL),
    )


def _tool(name: str, calls: list[ToolCallRecord]) -> ToolSummary:
    return ToolSummary(
        tool=name,
        uses=len(calls),
        refused=sum(1 for call in calls if call.refusal is not None),
        instances=len({call.instance for call in calls}),
    )


def quality_report(name: str, data: ProjectData) -> QualityReport:
    tickets = {ticket.id: ticket for ticket in data.tickets}
    records = sorted(data.checks, key=lambda record: record.seq)
    checks = [
        _check(check, group)
        for check, group in sums.groups(records, lambda record: record.check_name).items()
    ]
    failures = [
        CheckFailure(
            at=record.at,
            check_name=record.check_name,
            ticket_id=record.ticket_id,
            title=tickets[record.ticket_id].title if record.ticket_id in tickets else "",
            phase=ticket_phase(tickets[record.ticket_id]) if record.ticket_id in tickets else "",
            file=record.file,
            signer=record.signer,
            reason=record.reason,
        )
        for record in records
        if record.result == FAIL
    ]
    calls = sorted(data.tool_calls, key=lambda call: call.seq)
    tools = [_tool(tool, group) for tool, group in sums.groups(calls, lambda call: call.tool).items()]
    first: dict[str, Call] = {}
    for item in sorted(data.calls, key=lambda item: item.seq):
        first.setdefault(item.instance, item)
    began = {instance: datetime.fromisoformat(item.at) for instance, item in first.items()}
    refused = [call for call in calls if call.refusal is not None]
    refused.sort(
        key=lambda call: (call.instance not in began, began.get(call.instance, datetime.max), call.seq)
    )
    return QualityReport(
        project=name,
        subjects=sum(item.subjects for item in checks),
        first_pass=sum(item.first_pass for item in checks),
        checks=sorted(checks, key=lambda item: (-item.failed, -item.runs, item.check_name)),
        failures=failures,
        uses=len(calls),
        refused=len(refused),
        tools=sorted(tools, key=lambda item: (-item.refused, -item.uses, item.tool)),
        refusals=[
            Refusal(
                instance=call.instance,
                ticket_id=first[call.instance].ticket_id if call.instance in first else "",
                role=first[call.instance].role if call.instance in first else "",
                phase=first[call.instance].phase if call.instance in first else "",
                turn=call.turn,
                tool=call.tool,
                message=call.refusal or "",
            )
            for call in refused
        ],
        blocked=sum(1 for ticket in data.tickets if ticket.status == Status.BLOCKED),
        setbacks=setbacks(data.events, tickets),
    )
