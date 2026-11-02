"""Unico punto di scrittura dei registri. L'attore lo fornisce l'harness, mai l'agente."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import event as sa_event
from sqlalchemy import func
from sqlmodel import Session, col, create_engine, select

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
    ConceptRow,
    DerivationRow,
    EventRow,
    EvidenceRow,
    GateRow,
    OperationRow,
    ProjectRow,
    RenderRow,
    RunRow,
    TicketRow,
    UsageRow,
)

BUSY_SECONDS = schema.BUSY_SECONDS


class IllegalTransition(Exception):
    """L'azione non è prevista dallo stato attuale."""


class ForbiddenAction(Exception):
    """L'attore non ha il diritto di compiere l'azione."""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": BUSY_SECONDS})
        self._chain = threading.RLock()  # la catena di hash ha un solo scrittore per volta
        sa_event.listen(self.engine, "connect", self._configure)
        schema.ensure_current(self.engine)

    @staticmethod
    def _configure(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        deadline = time.monotonic() + BUSY_SECONDS
        while True:  # il passaggio a WAL non rispetta il timeout: chi arriva secondo riprova
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
        """Scrittura sulla catena di hash: il lucchetto del database vale anche tra processi diversi."""
        with self._chain, Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield session

    def _append(self, session: Session, ticket_id: str, actor: str, action: str, note: str) -> None:
        last = session.exec(select(EventRow).order_by(col(EventRow.seq).desc())).first()
        prev = last.hash if last else chain.GENESIS
        at = now()
        session.add(
            EventRow(
                ticket_id=ticket_id,
                at=at,
                actor=actor,
                action=action,
                note=note,
                prev_hash=prev,
                hash=chain.digest(prev, ticket_id, at, actor, action, note),
            )
        )

    # Progetti

    def project(self, name: str) -> ProjectRow | None:
        with Session(self.engine) as session:
            return session.get(ProjectRow, name)

    def set_project(self, name: str, budget_usd: float, model: str = "", effort: str = "") -> None:
        with Session(self.engine) as session:
            session.merge(ProjectRow(name=name, budget_usd=budget_usd, model=model, effort=effort))
            session.commit()

    def set_budget(self, name: str, budget_usd: float) -> None:
        with Session(self.engine) as session:
            row = session.get(ProjectRow, name)
            if row is None:
                raise KeyError(name)
            row.budget_usd = budget_usd
            session.add(row)
            session.commit()

    # Ticket

    def open(
        self,
        spec: TicketSpec,
        project: str = "default",
        inputs: dict[str, str] | None = None,
        operation: tuple[str, str, str] | None = None,
    ) -> str:
        """`inputs` sono gli hash all'apertura. `operation` (id, istanza, strumento) rende l'apertura
        e la sua registrazione un solo passo: alla ripresa il ticket non si duplica."""
        with self._writing() as session:
            count = session.exec(select(func.count()).select_from(TicketRow)).one()
            ticket_id = f"T-{count + 1:04d}"
            session.add(
                TicketRow(
                    id=ticket_id,
                    project=project,
                    spec_json=spec.model_dump_json(),
                    status=Status.OPEN.value,
                    inputs_json=json.dumps(inputs or {}),
                    created_at=now(),
                )
            )
            self._append(session, ticket_id, spec.sender, "open", spec.title)
            if operation:
                operation_id, instance, tool = operation
                result = json.dumps({"ok": True, "ticket": ticket_id}, ensure_ascii=False)
                session.add(
                    OperationRow(id=operation_id, instance=instance, tool=tool, result_json=result, at=now())
                )
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
            rows = session.exec(select(TicketRow).order_by(TicketRow.id)).all()
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
            query = select(TicketRow).where(TicketRow.project == project).order_by(TicketRow.id)
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
            self._append(session, ticket_id, actor, action.value, note)
            session.commit()
            return target

    def history(self, ticket_id: str) -> list[EventRow]:
        with Session(self.engine) as session:
            query = select(EventRow).where(EventRow.ticket_id == ticket_id).order_by(col(EventRow.seq))
            return list(session.exec(query).all())

    def verify_chain(self) -> bool:
        with Session(self.engine) as session:
            return chain.intact(session.exec(select(EventRow).order_by(col(EventRow.seq))).all())

    # Consumi

    def record_usage(self, row: UsageRow) -> None:
        with Session(self.engine) as session:
            session.add(row)
            session.commit()

    def spent(self, project: str, ticket_id: str | None = None) -> float:
        with Session(self.engine) as session:
            query = select(func.coalesce(func.sum(UsageRow.cost_usd), 0.0)).where(UsageRow.project == project)
            if ticket_id:
                query = query.where(UsageRow.ticket_id == ticket_id)
            return float(session.exec(query).one())

    def usage(self, project: str) -> list[UsageRow]:
        with Session(self.engine) as session:
            query = select(UsageRow).where(UsageRow.project == project).order_by(col(UsageRow.seq))
            return list(session.exec(query).all())

    # Prove

    def add_evidence(self, row: EvidenceRow) -> None:
        with self._writing() as session:
            session.add(row)
            note = f"{row.file}:{row.check_name}:{row.result}:{row.sha256[:16]}"
            self._append(session, row.ticket_id or "-", row.signer, "evidence", note)
            session.commit()

    def evidence(self, project: str) -> list[EvidenceRow]:
        with Session(self.engine) as session:
            query = select(EvidenceRow).where(EvidenceRow.project == project).order_by(col(EvidenceRow.seq))
            return list(session.exec(query).all())

    def add_render(self, project: str, source: str, source_sha: str, proofs: Iterable[str]) -> None:
        with Session(self.engine) as session:
            for proof in proofs:
                session.add(
                    RenderRow(at=now(), project=project, source=source, source_sha=source_sha, proof=proof)
                )
            session.commit()

    def render_of(self, project: str, source: str, source_sha: str) -> str | None:
        with Session(self.engine) as session:
            query = (
                select(RenderRow)
                .where(
                    RenderRow.project == project,
                    RenderRow.source == source,
                    RenderRow.source_sha == source_sha,
                )
                .order_by(col(RenderRow.seq).desc())
            )
            row = session.exec(query).first()
            return row.proof if row else None

    def renders_of(self, project: str, source: str, source_sha: str) -> list[str]:
        with Session(self.engine) as session:
            query = select(RenderRow).where(
                RenderRow.project == project,
                RenderRow.source == source,
                RenderRow.source_sha == source_sha,
            )
            return [row.proof for row in session.exec(query).all()]

    def add_derivation(self, row: DerivationRow) -> None:
        with Session(self.engine) as session:
            session.add(row)
            session.commit()

    def derivations(self, project: str, export: str) -> list[DerivationRow]:
        with Session(self.engine) as session:
            query = select(DerivationRow).where(
                DerivationRow.project == project, DerivationRow.export == export
            )
            return list(session.exec(query).all())

    # Idee e gate

    def add_concept(self, row: ConceptRow) -> None:
        with Session(self.engine) as session:
            session.add(row)
            session.commit()

    def concepts(self, project: str, round_: int | None = None) -> list[ConceptRow]:
        with Session(self.engine) as session:
            query = select(ConceptRow).where(ConceptRow.project == project)
            if round_ is not None:
                query = query.where(ConceptRow.round == round_)
            return list(session.exec(query.order_by(col(ConceptRow.seq))).all())

    def update_concept(self, idea_ticket: str, **fields: object) -> None:
        with Session(self.engine) as session:
            row = session.exec(select(ConceptRow).where(ConceptRow.idea_ticket == idea_ticket)).one()
            for name, value in fields.items():
                setattr(row, name, value)
            session.add(row)
            session.commit()

    def add_gate(self, row: GateRow) -> None:
        with Session(self.engine) as session:
            session.add(row)
            session.commit()

    def gates(self, project: str) -> list[GateRow]:
        with Session(self.engine) as session:
            query = select(GateRow).where(GateRow.project == project).order_by(col(GateRow.seq))
            return list(session.exec(query).all())

    # Operazioni, per la ripresa senza doppi effetti

    def operation(self, operation_id: str) -> str | None:
        with Session(self.engine) as session:
            row = session.get(OperationRow, operation_id)
            return row.result_json if row else None

    def operations(self, instance: str) -> list[OperationRow]:
        with Session(self.engine) as session:
            query = select(OperationRow).where(OperationRow.instance == instance)
            return list(session.exec(query).all())

    def record_operation(self, operation_id: str, instance: str, tool: str, result_json: str) -> None:
        with Session(self.engine) as session:
            session.merge(
                OperationRow(id=operation_id, instance=instance, tool=tool, result_json=result_json, at=now())
            )
            session.commit()

    # Esecuzioni

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
