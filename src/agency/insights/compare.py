"""La vista Confronto: due progetti affiancati, cosa è cambiato nell'impronta, e i giudizi alla cieca.

Un progetto è il lavoro su un brief, fatto da una o più esecuzioni (`run`, `resume`, `decide`), ognuna con
la sua impronta (ADR-0026). I numeri di ogni lato vengono dalle viste Run, Fasi, Modello e Strumenti e QA:
qui non si ricalcola niente. Le impronte confrontate sono l'ultima del progetto di prima e la prima di
quello di dopo: le differenze dicono cosa è cambiato fra la fine dell'uno e l'inizio dell'altro.

Un giudizio alla cieca conta per il confronto quando contiene file di tutti e due i progetti; si mostra con
tutti i suoi voti, anche quelli su file di altri progetti o esterni.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, ValidationError

from agency.contracts.run import Fingerprint, changes
from agency.insights import sums
from agency.insights.behaviour import behaviour_report
from agency.insights.domain import Call, JudgmentRecord, Provenance, RunRecord
from agency.insights.flow import flow_report
from agency.insights.ports import ProjectData
from agency.insights.quality import quality_report
from agency.insights.views import Milestone, project_report


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Compared(StrEnum):
    """Quali impronte ci sono: le esecuzioni prima di M1.6 non la hanno."""

    BOTH = "entrambe"
    NOT_BEFORE = "manca prima"
    NOT_AFTER = "manca dopo"
    NEITHER = "nessuna"


class Execution(_View):
    """Un'esecuzione: il comando, l'impronta, quanto ha speso, e quante differenze ha dalla precedente
    leggibile. `readable` è falso per un'impronta di una forma che questa versione non conosce."""

    seq: int
    at: str
    command: str
    digest: str
    readable: bool
    calls: int
    cost_usd: float
    changes_from_previous: int | None


class Side(_View):
    """Un progetto: `model` ed `effort` vuoti sono i predefiniti, `None` un progetto senza la sua riga, di
    prima di M1.5."""

    project: str
    model: str | None
    effort: str | None
    budget_usd: float | None
    delivery_status: str | None
    cost_usd: float
    calls: int
    instances: int
    working_minutes: float
    waiting_minutes: float
    to_presentation: Milestone | None
    cache_hit: float
    mean_context: float
    peak_context: int
    redone_usd: float
    blocked_usd: float
    subjects: int
    first_pass: int
    tool_uses: int
    tool_refusals: int
    executions: list[Execution]
    unrecorded_calls: int


class ChangeView(_View):
    """Una differenza fra due impronte: `None` vuol dire che da quella parte l'elemento non c'è."""

    part: str
    item: str
    before: str | None
    after: str | None


class FingerprintDiff(_View):
    state: Compared
    before_run: int | None
    after_run: int | None
    changes: list[ChangeView]


class PhasePair(_View):
    """Una fase dei due lati: `None` vuol dire che da quella parte la fase non c'è."""

    phase: str
    before_usd: float | None
    after_usd: float | None


class Vote(_View):
    letter: str
    project: str
    file: str
    level: str
    specific: bool
    best: bool
    why: str


class BlindComparison(_View):
    comparison: str
    at: str
    judge: str
    votes: list[Vote]


class CompareReport(_View):
    before: Side
    after: Side
    phases: list[PhasePair]
    fingerprint: FingerprintDiff
    judgments: list[BlindComparison]


def _fingerprint(run: RunRecord) -> Fingerprint | None:
    try:
        return Fingerprint.model_validate_json(run.fingerprint_json)
    except ValidationError:
        return None


def _executions(runs: list[RunRecord], calls: list[Call]) -> list[Execution]:
    by_run = sums.groups((call for call in calls if call.run is not None), lambda call: str(call.run))
    executions: list[Execution] = []
    previous: Fingerprint | None = None
    for run in sorted(runs, key=lambda run: run.seq):
        current = _fingerprint(run)
        spent = by_run.get(str(run.seq), [])
        executions.append(
            Execution(
                seq=run.seq,
                at=run.at,
                command=run.command,
                digest=run.digest,
                readable=current is not None,
                calls=len(spent),
                cost_usd=sums.cost(spent),
                changes_from_previous=(
                    len(changes(previous, current)) if previous is not None and current is not None else None
                ),
            )
        )
        if current is not None:
            previous = current
    return executions


def _side(name: str, data: ProjectData, provenance: Provenance) -> Side:
    report = project_report(name, data, provenance)
    flow, quality = flow_report(name, data), quality_report(name, data)
    behaviour = behaviour_report(name, data)
    return Side(
        project=name,
        model=report.model if data.project is not None else None,
        effort=report.effort if data.project is not None else None,
        budget_usd=report.budget_usd,
        delivery_status=flow.outcome.delivery_status,
        cost_usd=report.cost_usd,
        calls=report.calls,
        instances=len(report.instances),
        working_minutes=report.working_minutes,
        waiting_minutes=report.elapsed_minutes - report.working_minutes,
        to_presentation=report.to_presentation,
        cache_hit=report.cache_hit,
        mean_context=report.mean_context,
        peak_context=max((item.peak_context for item in behaviour.instances), default=0),
        redone_usd=sum(phase.redone_usd for phase in flow.phases),
        blocked_usd=sum(phase.blocked_usd for phase in flow.phases),
        subjects=quality.subjects,
        first_pass=quality.first_pass,
        tool_uses=quality.uses,
        tool_refusals=quality.refused,
        executions=_executions(data.runs, data.calls),
        unrecorded_calls=sum(1 for call in data.calls if call.run is None),
    )


def _readable(runs: list[RunRecord]) -> list[tuple[RunRecord, Fingerprint]]:
    found = [(run, _fingerprint(run)) for run in sorted(runs, key=lambda run: run.seq)]
    return [(run, print_) for run, print_ in found if print_ is not None]


def _diff(before: list[RunRecord], after: list[RunRecord]) -> FingerprintDiff:
    last, first = _readable(before)[-1:], _readable(after)[:1]
    if not last or not first:
        state = {
            (False, False): Compared.NEITHER,
            (False, True): Compared.NOT_BEFORE,
            (True, False): Compared.NOT_AFTER,
        }[(bool(last), bool(first))]
        return FingerprintDiff(
            state=state,
            before_run=last[0][0].seq if last else None,
            after_run=first[0][0].seq if first else None,
            changes=[],
        )
    (old_run, old), (new_run, new) = last[0], first[0]
    return FingerprintDiff(
        state=Compared.BOTH,
        before_run=old_run.seq,
        after_run=new_run.seq,
        changes=[
            ChangeView(part=item.part, item=item.item, before=item.before, after=item.after)
            for item in changes(old, new)
        ],
    )


def _phases(before: ProjectData, after: ProjectData, names: tuple[str, str]) -> list[PhasePair]:
    old = {phase.phase: phase.cost_usd for phase in flow_report(names[0], before).phases}
    new = {phase.phase: phase.cost_usd for phase in flow_report(names[1], after).phases}
    order = [*new, *(phase for phase in old if phase not in new)]
    return [PhasePair(phase=phase, before_usd=old.get(phase), after_usd=new.get(phase)) for phase in order]


def _judgments(judgments: list[JudgmentRecord], names: tuple[str, str]) -> list[BlindComparison]:
    found = []
    for comparison, votes in sums.groups(
        sorted(judgments, key=lambda item: item.seq), lambda item: item.comparison
    ).items():
        if not set(names) <= {vote.project for vote in votes}:
            continue
        found.append(
            BlindComparison(
                comparison=comparison,
                at=votes[0].at,
                judge=votes[0].judge,
                votes=[
                    Vote(
                        letter=vote.letter,
                        project=vote.project,
                        file=vote.file,
                        level=vote.level,
                        specific=vote.specific,
                        best=vote.best,
                        why=vote.why,
                    )
                    for vote in sorted(votes, key=lambda item: item.letter)
                ],
            )
        )
    return found


def compare_report(
    before_name: str,
    before: ProjectData,
    after_name: str,
    after: ProjectData,
    judgments: list[JudgmentRecord],
    provenance: Provenance,
) -> CompareReport:
    names = (before_name, after_name)
    return CompareReport(
        before=_side(before_name, before, provenance),
        after=_side(after_name, after, provenance),
        phases=_phases(before, after, names),
        fingerprint=_diff(before.runs, after.runs),
        judgments=_judgments(judgments, names),
    )
