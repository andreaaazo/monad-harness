"""The only place that writes the registry. The harness supplies the actor, never the agent."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, col, create_engine, select

from agency.contracts.clock import now
from agency.contracts.judgment import Judged, Judgment
from agency.contracts.ledger import ForbiddenAction, IllegalTransition
from agency.contracts.run import Fingerprint, RunCommand
from agency.contracts.ticket import (
    REVIEW_TYPES,
    TRANSITIONS,
    Action,
    Status,
    TicketSpec,
    Verdict,
)
from agency.ledger import chain, schema
from agency.ledger.models import (
    ArtifactRow,
    ConceptRow,
    DerivationRow,
    EventRow,
    EvidenceRow,
    GateRow,
    JudgmentRow,
    OperationRow,
    ProjectRow,
    RenderRow,
    RunRow,
    TicketRow,
    UsageRow,
)

BUSY_SECONDS = schema.BUSY_SECONDS
NO_TICKET = "-"  # the ticket of an event that belongs to none
HARNESS = "harness"  # the actor of the events that bind a row: the harness writes those rows
type BoundRow = ConceptRow | GateRow | EvidenceRow | UsageRow | ProjectRow
# The rows an event binds whole besides its ticket: their key in `payload_json`, how verify names them, and
# the column that tells one row from another, with its type (ADR-0049, ADR-0050).
BOUND_ROWS: dict[type[BoundRow], tuple[str, str, str, type[int] | type[str]]] = {
    ConceptRow: ("concept", "idea", "seq", int),
    GateRow: ("gate", "gate", "seq", int),
    EvidenceRow: ("evidence", "prova", "seq", int),
    UsageRow: ("usage", "consumo", "seq", int),
    ProjectRow: ("project", "progetto", "name", str),
}


class LedgerMissing(Exception):
    """There is no registry at the path: a command that only reads or amends must not create one."""

    def __init__(self, path: Path) -> None:
        self.path = path.absolute()
        super().__init__(f"nessun registro in {self.path}")


def require_registry(path: Path) -> None:
    """Raises `LedgerMissing` when there is no registry file at `path`."""
    if not path.is_file():
        raise LedgerMissing(path)


def _parsed(text: str) -> object:
    """JSON from a row that may have been tampered with: None when it does not parse, so verify reports it."""
    try:
        return json.loads(text)
    except ValueError:
        return None


def _bound_rows(events: Iterable[EventRow]) -> dict[str, dict[int | str, object]]:
    """Each bound row, by key and identity (its seq, a project's name), as the last version-2 event that binds
    it left it."""
    bound: dict[str, dict[int | str, object]] = {key: {} for key, *_ in BOUND_ROWS.values()}
    for event in events:  # in chain order: a later binding of the same row wins
        payload = _parsed(event.payload_json) if event.version == 2 else None
        if not isinstance(payload, dict):
            continue
        for key, _, column, kind in BOUND_ROWS.values():
            row = payload.get(key)
            if isinstance(row, dict) and isinstance(row.get(column), kind):
                bound[key][row[column]] = row
    return bound


def _bound_tickets(events: Iterable[EventRow]) -> list[str]:
    """The tickets whose state a version-2 event binds, in chain order: each had a row when that event was
    written."""
    found: dict[str, None] = {}
    for event in events:
        payload = _parsed(event.payload_json) if event.version == 2 else None
        if isinstance(payload, dict) and "status" in payload:
            found.setdefault(event.ticket_id, None)
    return list(found)


def _bound_projects(events: Iterable[EventRow]) -> dict[str, set[str]]:
    """Each ticket's projects, as every version-2 event of it binds one. A ticket never changes project
    (ADR-0053), so a second value is tampering; events from before the revision 0009 bind none."""
    found: dict[str, set[str]] = {}
    for event in events:
        payload = _parsed(event.payload_json) if event.version == 2 else None
        if isinstance(payload, dict) and isinstance(payload.get("project"), str):
            found.setdefault(event.ticket_id, set()).add(payload["project"])
    return found


def _stored(session: Session, model: type[BoundRow], column: str) -> list[dict[str, Any]]:
    """The rows of `model`'s table, in `column` order, as SQLite stores them, without the models'
    conversions: `approved = 'no'` reads back through the model as True, the value a gate binds, yet it is not
    what was written."""
    columns = list(model.model_fields)
    query = f"SELECT {', '.join(columns)} FROM {model.__tablename__} ORDER BY {column}"
    return [dict(zip(columns, values, strict=True)) for values in session.connection().exec_driver_sql(query)]


def _row_mismatches(
    label: str, column: str, rows: Sequence[dict[str, Any]], bound: dict[Any, object]
) -> list[str]:
    """One line per row the chain does not bind or binds differently, and per bound row the table lost; each
    row named by `column`. A stored 0 or 1 equals the False or True a binding holds."""
    found: list[str] = []
    for row in rows:
        if row[column] not in bound:
            found.append(f"{label} {row[column]}: riga non legata alla catena")
        elif bound[row[column]] != row:
            found.append(f"{label} {row[column]}: riga diversa dalla catena")
    present = {row[column] for row in rows}
    found += [f"{label} {identity}: mancante nel registro" for identity in sorted(bound.keys() - present)]
    return found


class Ledger:
    """The registry's only writer. A ticket change, and every idea, gate, proof, paid call and project it
    writes, appends a chain event in the same transaction. Renders, derivations, operations, runs, judgments
    and artifacts are rows outside the chain."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": BUSY_SECONDS})
        self._chain = threading.RLock()  # the hash chain has one writer at a time
        sa_event.listen(self.engine, "connect", self._configure)
        schema.ensure_current(self.engine)

    @classmethod
    def existing(cls, path: Path) -> Ledger:
        """Open a registry that must already exist; only `agency run` may create one (DX-003)."""
        require_registry(path)
        return cls(path)

    @staticmethod
    def _configure(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        deadline = time.monotonic() + BUSY_SECONDS
        while True:  # switching to WAL ignores the timeout: whoever comes second retries
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @contextmanager
    def _writing(self) -> Iterator[Session]:
        """A write on the hash chain: the database lock also holds between processes."""
        with self._chain, Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield session

    def _append(
        self,
        session: Session,
        ticket_id: str,
        actor: str,
        action: str,
        note: str,
        ticket: TicketRow | None,
        row: BoundRow | None = None,
    ) -> None:
        """`ticket` is the row as this event leaves it: the event binds its state, the sha256 of its contract
        and its project into the chain (ADR-0047, ADR-0049, ADR-0053). `row` is an idea, a gate, a proof, a
        paid call or a project just written and flushed: the event binds it whole (ADR-0049, ADR-0050). An
        event with neither binds an empty payload."""
        last = session.exec(select(EventRow).order_by(col(EventRow.seq).desc())).first()
        prev = last.hash if last else chain.GENESIS
        at = now()
        binding: dict[str, object] = {}
        if ticket is not None:
            binding |= chain.ticket_binding(
                ticket.status,
                ticket.verdict,
                json.loads(ticket.delivered_json),
                ticket.spec_json,
                ticket.inputs_json,
                ticket.project,
            )
        if row is not None:
            binding[BOUND_ROWS[type(row)][0]] = row.model_dump()
        payload_json = chain.canonical(binding) if binding else ""
        session.add(
            EventRow(
                ticket_id=ticket_id,
                at=at,
                actor=actor,
                action=action,
                note=note,
                prev_hash=prev,
                hash=chain.digest_v2(prev, ticket_id, at, actor, action, note, payload_json),
                version=2,
                payload_json=payload_json,
            )
        )

    # Projects

    def project(self, name: str) -> ProjectRow | None:
        with Session(self.engine) as session:
            return session.get(ProjectRow, name)

    def set_project(self, name: str, budget_usd: float, model: str = "", effort: str = "") -> None:
        """Every write of a project binds the row as it leaves it, outside any ticket (ADR-0050)."""
        with self._writing() as session:
            row = session.merge(ProjectRow(name=name, budget_usd=budget_usd, model=model, effort=effort))
            session.flush()
            self._append(session, NO_TICKET, HARNESS, "project", "", None, row)
            session.commit()

    def set_budget(self, name: str, budget_usd: float) -> None:
        with self._writing() as session:
            row = session.get(ProjectRow, name)
            if row is None:
                raise KeyError(name)
            row.budget_usd = budget_usd
            session.add(row)
            session.flush()
            self._append(session, NO_TICKET, HARNESS, "project", "", None, row)
            session.commit()

    # Tickets

    def open(
        self,
        spec: TicketSpec,
        project: str = "default",
        inputs: dict[str, str] | None = None,
        operation: tuple[str, str, str] | None = None,
        concept: ConceptRow | None = None,
    ) -> str:
        """`inputs` are the hashes at opening. `operation` (id, instance, tool) makes the opening and its
        record one step: on resume the ticket is not opened twice.

        `concept` is written in the same transaction as the ticket, so an interruption cannot leave a ticket
        without its concept row. The caller cannot know the new ticket id, so `open` sets
        `concept.idea_ticket` to it."""
        with self._writing() as session:
            count = session.exec(select(func.count()).select_from(TicketRow)).one()
            ticket_id = f"T-{count + 1:04d}"
            row = TicketRow(
                id=ticket_id,
                project=project,
                spec_json=spec.model_dump_json(),
                status=Status.OPEN.value,
                inputs_json=json.dumps(inputs or {}),
                created_at=now(),
            )
            session.add(row)
            self._append(session, ticket_id, spec.sender, "open", spec.title, row)
            if operation:
                operation_id, instance, tool = operation
                result = json.dumps({"ok": True, "ticket": ticket_id}, ensure_ascii=False)
                session.add(
                    OperationRow(id=operation_id, instance=instance, tool=tool, result_json=result, at=now())
                )
            if concept is not None:
                concept.idea_ticket = ticket_id
                session.add(concept)
                session.flush()
                self._append(session, NO_TICKET, HARNESS, "concept", "", None, concept)
            session.commit()
        return ticket_id

    def inputs(self, ticket_id: str) -> dict[str, str]:
        with Session(self.engine) as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            return json.loads(row.inputs_json)

    def project_of(self, ticket_id: str) -> str:
        with Session(self.engine) as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            return row.project

    def children(self, ticket_id: str) -> list[str]:
        with Session(self.engine) as session:
            rows = session.exec(select(TicketRow).order_by(literal_column("rowid"))).all()
            return [r.id for r in rows if TicketSpec.model_validate_json(r.spec_json).parent == ticket_id]

    def spec(self, ticket_id: str) -> TicketSpec:
        with Session(self.engine) as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            return TicketSpec.model_validate_json(row.spec_json)

    def status(self, ticket_id: str) -> tuple[Status, Verdict | None]:
        with Session(self.engine) as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            return Status(row.status), Verdict(row.verdict) if row.verdict else None

    def delivered(self, ticket_id: str) -> dict[str, str]:
        with Session(self.engine) as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            return json.loads(row.delivered_json)

    def tickets(self, project: str) -> list[TicketRow]:
        with Session(self.engine) as session:
            query = select(TicketRow).where(TicketRow.project == project).order_by(literal_column("rowid"))
            return list(session.exec(query).all())

    def apply(
        self,
        ticket_id: str,
        action: Action,
        actor: str,
        note: str = "",
        verdict: Verdict | None = None,
        delivered: dict[str, str] | None = None,
    ) -> Status:
        """Moves the ticket by `TRANSITIONS`, if the actor's party may and, for a review, with its verdict.
        The event binds the state the ticket is left in."""
        allowed_from, target, party = TRANSITIONS[action]
        with self._writing() as session:
            row = session.get(TicketRow, ticket_id)
            if row is None:
                raise KeyError(ticket_id)
            spec = TicketSpec.model_validate_json(row.spec_json)
            parties = {
                "sender": {spec.sender},
                "assignee": {spec.assignee},
                "either": {spec.sender, spec.assignee},
            }[party]
            if actor not in parties:
                raise ForbiddenAction(f"{action.value} spetta a {sorted(parties)}, non a {actor}")
            if Status(row.status) not in allowed_from:
                raise IllegalTransition(f"{action.value} non è ammesso da {row.status}")
            is_review = spec.type in REVIEW_TYPES
            if action is Action.DELIVER and is_review and verdict is None:
                raise IllegalTransition("una revisione si consegna con un verdetto")
            if verdict is not None and not (action is Action.DELIVER and is_review):
                raise IllegalTransition("il verdetto vale solo alla consegna di qa e revisione")
            row.status = target.value
            if verdict is not None:
                row.verdict = verdict.value
            elif action is Action.REWORK:
                row.verdict = None
            if delivered is not None:
                row.delivered_json = json.dumps(delivered)
            session.add(row)
            self._append(session, ticket_id, actor, action.value, note, row)
            session.commit()
            return target

    def history(self, ticket_id: str) -> list[EventRow]:
        with Session(self.engine) as session:
            query = select(EventRow).where(EventRow.ticket_id == ticket_id).order_by(col(EventRow.seq))
            return list(session.exec(query).all())

    def verify_chain(self) -> bool:
        with Session(self.engine) as session:
            return chain.intact(session.exec(select(EventRow).order_by(col(EventRow.seq))).all())

    def replay_mismatches(self) -> list[str]:
        """Each ticket against the state, contract and project its last event binds, and each idea, gate,
        proof, paid call and project against the last event that binds it: those tables are projections of
        the chain, and a difference is tampering (ADR-0047, ADR-0049, ADR-0050, ADR-0053). One line per row
        the chain does not bind, per field that differs, and per bound ticket or row that is gone."""
        with Session(self.engine) as session:
            events = session.exec(select(EventRow).order_by(col(EventRow.seq))).all()
            tickets = session.exec(select(TicketRow).order_by(literal_column("rowid"))).all()
            rows = {model: _stored(session, model, column) for model, (_, _, column, _) in BOUND_ROWS.items()}
        last = {event.ticket_id: event for event in events}
        projects = _bound_projects(events)
        found: list[str] = []
        for ticket in tickets:
            event = last.get(ticket.id)
            bound = _parsed(event.payload_json) if event is not None and event.version == 2 else None
            if not isinstance(bound, dict):
                found.append(f"{ticket.id}: stato non legato alla catena")
                continue
            if bound.get("status") != ticket.status:
                found.append(f"{ticket.id}: stato diverso dalla catena")
            if bound.get("verdict") != ticket.verdict:
                found.append(f"{ticket.id}: verdetto diverso dalla catena")
            if bound.get("delivered") != _parsed(ticket.delivered_json):
                found.append(f"{ticket.id}: consegna diversa dalla catena")
            if bound.get("spec_sha256") != chain.text_sha256(ticket.spec_json):
                found.append(f"{ticket.id}: contratto diverso dalla catena")
            if bound.get("inputs_sha256") != chain.text_sha256(ticket.inputs_json):
                found.append(f"{ticket.id}: hash d'apertura diversi dalla catena")
            # Every event, not only the last: a later event binds the row as it finds it, and would hide a
            # moved project behind the first call its agents make in the other folder (ADR-0054).
            others = projects.get(ticket.id, set()) - {ticket.project}
            if bound.get("project") != ticket.project or others:
                found.append(f"{ticket.id}: progetto diverso dalla catena")
        present = {ticket.id for ticket in tickets}
        found += [
            f"{ticket_id}: ticket mancante nel registro"
            for ticket_id in _bound_tickets(events)
            if ticket_id not in present
        ]
        bound_rows = _bound_rows(events)
        for model, (key, label, column, _) in BOUND_ROWS.items():
            found += _row_mismatches(label, column, rows[model], bound_rows[key])
        return found

    # Usage

    def record_usage(self, row: UsageRow) -> None:
        """A paid call and the event that binds it, in one transaction (ADR-0050). The event stays on the
        call's ticket with the ticket's state, as a proof's does; a call without a ticket binds only
        itself."""
        with self._writing() as session:
            session.add(row)
            session.flush()
            ticket = session.get(TicketRow, row.ticket_id) if row.ticket_id else None
            self._append(session, row.ticket_id or NO_TICKET, HARNESS, "usage", "", ticket, row)
            session.commit()

    def spent(self, project: str) -> float:
        with Session(self.engine) as session:
            query = select(func.coalesce(func.sum(UsageRow.cost_usd), 0.0)).where(UsageRow.project == project)
            return float(session.exec(query).one())

    def usage(self, project: str) -> list[UsageRow]:
        with Session(self.engine) as session:
            query = select(UsageRow).where(UsageRow.project == project).order_by(col(UsageRow.seq))
            return list(session.exec(query).all())

    # Proofs

    def add_evidence(self, row: EvidenceRow, operation: tuple[str, str, str, str] | None = None) -> None:
        """`operation` (id, instance, tool, result) makes the proof and its resume record one transaction, as
        in `open`: a replay after a crash finds the record and does not add the proof twice."""
        with self._writing() as session:
            session.add(row)
            session.flush()
            note = f"{row.file}:{row.check_name}:{row.result}:{row.sha256[:16]}"
            ticket = session.get(TicketRow, row.ticket_id) if row.ticket_id else None
            self._append(session, row.ticket_id or NO_TICKET, row.signer, "evidence", note, ticket, row)
            if operation:
                operation_id, instance, tool, result = operation
                session.add(
                    OperationRow(id=operation_id, instance=instance, tool=tool, result_json=result, at=now())
                )
            session.commit()

    def evidence(self, project: str) -> list[EvidenceRow]:
        with Session(self.engine) as session:
            query = select(EvidenceRow).where(EvidenceRow.project == project).order_by(col(EvidenceRow.seq))
            return list(session.exec(query).all())

    def add_render(self, project: str, source: str, source_sha: str, proofs: Iterable[str]) -> None:
        """A proof already stored for this source version is not stored again: a replay adds nothing."""
        with self._writing() as session:
            for proof in proofs:
                same = select(RenderRow).where(
                    RenderRow.project == project,
                    RenderRow.source == source,
                    RenderRow.source_sha == source_sha,
                    RenderRow.proof == proof,
                )
                if session.exec(same).first() is None:
                    session.add(
                        RenderRow(
                            at=now(), project=project, source=source, source_sha=source_sha, proof=proof
                        )
                    )
            session.commit()

    def renders_of(self, project: str, source: str, source_sha: str) -> list[str]:
        with Session(self.engine) as session:
            query = select(RenderRow).where(
                RenderRow.project == project,
                RenderRow.source == source,
                RenderRow.source_sha == source_sha,
            )
            return [row.proof for row in session.exec(query).all()]

    def add_derivation(self, row: DerivationRow) -> None:
        """A link identical to a stored one (every column but `seq` and `at`) is not stored again."""
        with self._writing() as session:
            same = select(DerivationRow).where(
                DerivationRow.project == row.project,
                DerivationRow.master == row.master,
                DerivationRow.master_sha == row.master_sha,
                DerivationRow.export == row.export,
                DerivationRow.export_sha == row.export_sha,
                DerivationRow.how == row.how,
            )
            if session.exec(same).first() is None:
                session.add(row)
                session.commit()

    def derivations(self, project: str, export: str) -> list[DerivationRow]:
        with Session(self.engine) as session:
            query = select(DerivationRow).where(
                DerivationRow.project == project, DerivationRow.export == export
            )
            return list(session.exec(query).all())

    # Ideas and gates

    def concepts(self, project: str, round_: int | None = None) -> list[ConceptRow]:
        with Session(self.engine) as session:
            query = select(ConceptRow).where(ConceptRow.project == project)
            if round_ is not None:
                query = query.where(ConceptRow.round == round_)
            return list(session.exec(query.order_by(col(ConceptRow.seq))).all())

    def update_concept(self, idea_ticket: str, **fields: object) -> None:
        """A write that changes nothing (every field already holds the value) is skipped, with its chain
        event: a replay after a crash does not repeat it."""
        with self._writing() as session:
            row = session.exec(select(ConceptRow).where(ConceptRow.idea_ticket == idea_ticket)).one()
            if all(getattr(row, name) == value for name, value in fields.items()):
                return
            for name, value in fields.items():
                setattr(row, name, value)
            session.add(row)
            session.flush()
            self._append(session, NO_TICKET, HARNESS, "concept", "", None, row)
            session.commit()

    def add_gate(self, row: GateRow) -> None:
        with self._writing() as session:
            session.add(row)
            session.flush()
            self._append(session, NO_TICKET, HARNESS, "gate", "", None, row)
            session.commit()

    def gates(self, project: str) -> list[GateRow]:
        with Session(self.engine) as session:
            query = select(GateRow).where(GateRow.project == project).order_by(col(GateRow.seq))
            return list(session.exec(query).all())

    # Operations, so a resume has no double effects

    def operation(self, operation_id: str) -> str | None:
        with Session(self.engine) as session:
            row = session.get(OperationRow, operation_id)
            return row.result_json if row else None

    def operations(self, instance: str) -> list[OperationRow]:
        with Session(self.engine) as session:
            query = select(OperationRow).where(OperationRow.instance == instance)
            return list(session.exec(query).all())

    def record_operation(self, operation_id: str, instance: str, tool: str, result_json: str) -> None:
        """The first record of an operation id stays: a replay reruns only the tools without an effect, and
        the harness has already acted on the first record (ADR-0050)."""
        row = OperationRow(id=operation_id, instance=instance, tool=tool, result_json=result_json, at=now())
        with Session(self.engine) as session:
            session.execute(insert(OperationRow).values(row.model_dump()).on_conflict_do_nothing(["id"]))
            session.commit()

    # Runs

    def record_run(self, project: str, command: RunCommand, fingerprint: Fingerprint) -> int:
        row = RunRow(
            at=now(),
            project=project,
            command=command.value,
            digest=fingerprint.digest(),
            fingerprint_json=fingerprint.model_dump_json(),
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        assert row.seq is not None
        return row.seq

    def runs(self, project: str) -> list[RunRow]:
        with Session(self.engine) as session:
            query = select(RunRow).where(RunRow.project == project).order_by(col(RunRow.seq))
            return list(session.exec(query).all())

    def run(self, seq: int) -> RunRow | None:
        with Session(self.engine) as session:
            return session.get(RunRow, seq)

    # Blind judgments

    def record_judgment(self, comparison: str, judgment: Judgment, files: dict[str, Judged]) -> None:
        """A whole comparison in one transaction: half a judgment never stays in the registry."""
        letters = [rating.letter for rating in judgment.ratings]
        if sorted(files) != sorted(letters):
            raise ValueError(f"judged letters {letters}, letters with a file {sorted(files)}")
        at = now()
        with Session(self.engine) as session:
            for rating in judgment.ratings:
                judged = files[rating.letter]
                session.add(
                    JudgmentRow(
                        at=at,
                        comparison=comparison,
                        judge=judgment.judge,
                        letter=rating.letter,
                        project=judged.project,
                        file=judged.file,
                        sha256=judged.sha256,
                        level=rating.level.value,
                        specific=rating.specific,
                        best=rating.letter == judgment.best,
                        why=rating.why,
                    )
                )
            session.commit()

    def judgments(self, project: str) -> list[JudgmentRow]:
        with Session(self.engine) as session:
            query = select(JudgmentRow).where(JudgmentRow.project == project).order_by(col(JudgmentRow.seq))
            return list(session.exec(query).all())

    def comparison(self, comparison: str) -> list[JudgmentRow]:
        with Session(self.engine) as session:
            query = (
                select(JudgmentRow).where(JudgmentRow.comparison == comparison).order_by(col(JudgmentRow.seq))
            )
            return list(session.exec(query).all())

    # Artifacts

    def record_artifacts(self, rows: list[ArtifactRow]) -> None:
        """A version already recorded for the same file and reason is not recorded again."""
        if not rows:
            return
        values = [row.model_dump(exclude={"seq"}) for row in rows]
        with Session(self.engine) as session:
            session.execute(insert(ArtifactRow).values(values).on_conflict_do_nothing())
            session.commit()

    def artifacts(self, project: str) -> list[ArtifactRow]:
        with Session(self.engine) as session:
            query = select(ArtifactRow).where(ArtifactRow.project == project).order_by(col(ArtifactRow.seq))
            return list(session.exec(query).all())

    def artifacts_with(self, prefix: str) -> list[ArtifactRow]:
        with Session(self.engine) as session:
            query = select(ArtifactRow).where(col(ArtifactRow.sha256).startswith(prefix, autoescape=True))
            return list(session.exec(query.order_by(col(ArtifactRow.seq))).all())

    def all_artifacts(self) -> list[ArtifactRow]:
        with Session(self.engine) as session:
            return list(session.exec(select(ArtifactRow).order_by(col(ArtifactRow.seq))).all())
