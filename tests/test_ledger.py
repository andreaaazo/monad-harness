import itertools
import json
import threading
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import event as sa_event
from sqlalchemy import text
from sqlmodel import Session, col, select

from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.contracts.ledger import (
    ConceptEntry,
    DerivationEntry,
    EvidenceEntry,
    ForbiddenAction,
    GateEntry,
    IllegalTransition,
    LedgerPort,
    UsageEntry,
)
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType, Verdict
from agency.entrypoints import cli
from agency.ledger import Ledger, chain, store
from agency.ledger.models import EventRow, TicketRow
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Sandbox
from support.rules import RULES


def production(**extra: object) -> TicketSpec:
    base: dict[str, object] = {
        "title": "Segno",
        "request": "Disegna il segno",
        "type": TicketType.PRODUCTION,
        "sender": "design-director",
        "assignee": "identity-designer",
        "outputs": ["work/source/segno.vectorcraft"],
        "checks": {"*.vectorcraft": ["master_open"]},
        "media": [Medium.VECTOR],
    }
    return TicketSpec.model_validate(base | extra)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.sqlite")


def test_production_requires_medium() -> None:
    with pytest.raises(ValidationError):
        production(media=[])


def test_medium_none_requires_reason() -> None:
    with pytest.raises(ValidationError):
        production(media=[Medium.NONE])


def test_folder_output_is_rejected() -> None:
    with pytest.raises(ValidationError):
        production(outputs=["work/proofs/"])


def test_exemption_needs_a_reason() -> None:
    with pytest.raises(ValidationError):
        production(exempt={"work/a.md": "x"})


def test_lifecycle_records_actors(ledger: Ledger) -> None:
    ticket = ledger.open(production())
    ledger.apply(ticket, Action.DELIVER, "identity-designer")
    ledger.apply(ticket, Action.REWORK, "design-director", "taglio troppo sottile")
    ledger.apply(ticket, Action.DELIVER, "identity-designer")
    assert ledger.apply(ticket, Action.ACCEPT, "design-director") is Status.ACCEPTED
    assert [(e.action, e.actor) for e in ledger.history(ticket)] == [
        ("open", "design-director"),
        ("deliver", "identity-designer"),
        ("rework", "design-director"),
        ("deliver", "identity-designer"),
        ("accept", "design-director"),
    ]


def test_only_the_assignee_delivers(ledger: Ledger) -> None:
    ticket = ledger.open(production())
    with pytest.raises(ForbiddenAction):
        ledger.apply(ticket, Action.DELIVER, "critic")


def test_only_the_sender_accepts(ledger: Ledger) -> None:
    ticket = ledger.open(production())
    ledger.apply(ticket, Action.DELIVER, "identity-designer")
    with pytest.raises(ForbiddenAction):
        ledger.apply(ticket, Action.ACCEPT, "identity-designer")


def test_transition_outside_the_table_does_not_exist(ledger: Ledger) -> None:
    ticket = ledger.open(production())
    with pytest.raises(IllegalTransition):
        ledger.apply(ticket, Action.ACCEPT, "design-director")


def test_review_needs_a_verdict_and_keeps_it_apart_from_status(ledger: Ledger) -> None:
    ticket = ledger.open(
        production(type=TicketType.QA, assignee="qa-inspector", media=[], checks={"*.svg": ["svg_audit"]})
    )
    with pytest.raises(IllegalTransition):
        ledger.apply(ticket, Action.DELIVER, "qa-inspector")
    ledger.apply(ticket, Action.DELIVER, "qa-inspector", verdict=Verdict.REVISE)
    assert ledger.status(ticket) == (Status.DELIVERED, Verdict.REVISE)


def test_rework_clears_a_review_verdict(ledger: Ledger) -> None:
    """A review sent back loses its verdict: the dashboard must not keep showing READY (TST-014)."""
    ticket = ledger.open(
        production(type=TicketType.QA, assignee="qa-inspector", media=[], checks={"*.svg": ["svg_audit"]})
    )
    ledger.apply(ticket, Action.DELIVER, "qa-inspector", verdict=Verdict.READY)
    assert ledger.status(ticket) == (Status.DELIVERED, Verdict.READY)
    ledger.apply(ticket, Action.REWORK, "design-director", "rifai la verifica")
    assert ledger.status(ticket) == (Status.REWORK, None)


def test_production_cannot_carry_a_verdict(ledger: Ledger) -> None:
    ticket = ledger.open(production())
    with pytest.raises(IllegalTransition):
        ledger.apply(ticket, Action.DELIVER, "identity-designer", verdict=Verdict.READY)


def test_events_cannot_be_rewritten(ledger: Ledger) -> None:
    ledger.open(production())
    with ledger.engine.begin() as conn, pytest.raises(Exception, match="solo in aggiunta"):
        conn.execute(text("UPDATE events SET actor = 'critic'"))
    with ledger.engine.begin() as conn, pytest.raises(Exception, match="solo in aggiunta"):
        conn.execute(text("DELETE FROM events"))


def test_chain_detects_tampering_that_bypasses_the_triggers(ledger: Ledger) -> None:
    ledger.open(production())
    assert ledger.verify_chain()
    with ledger.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER events_no_update"))
        conn.execute(text("UPDATE events SET actor = 'critic'"))
    assert not ledger.verify_chain()


def use_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The CLI reads its settings from the environment: point it at a folder of the test's own."""
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data" / "ledger.sqlite"


def test_verify_exits_1_on_a_broken_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exit code, not only the message, reports tampering (TST-013)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ledger.open(production())
    assert cli.main(["verify"]) == 0
    with ledger.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER events_no_update"))
        conn.execute(text("UPDATE events SET actor = 'critic'"))
    capsys.readouterr()
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[0] == "REGISTRO ALTERATO"


def review() -> TicketSpec:
    return production(type=TicketType.QA, assignee="qa-inspector", media=[], checks={"*.svg": ["svg_audit"]})


DELIVERED = {"segno.svg": "a1b2"}
EMPTY_SHA256 = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"  # sha256 of the text {}


@pytest.mark.parametrize(
    ("column", "value", "line"),
    [
        ("verdict", "READY", "T-0001: verdetto diverso dalla catena"),
        ("status", "accepted", "T-0001: stato diverso dalla catena"),
        ("delivered_json", '{"segno.svg": "c3d4"}', "T-0001: consegna diversa dalla catena"),
    ],
)
def test_changing_a_verdict_in_tickets_breaks_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    column: str,
    value: str,
    line: str,
) -> None:
    """The verdict, the status and the delivered hashes are bound into the chain: `tickets` is only their
    projection, and a direct change of it is tampering (CMT-007, ADR-0047)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ticket = ledger.open(review())
    ledger.apply(ticket, Action.DELIVER, "qa-inspector", verdict=Verdict.REVISE, delivered=DELIVERED)
    assert cli.main(["verify"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "registro integro"

    with ledger.engine.begin() as conn:
        conn.execute(text(f"UPDATE tickets SET {column} = :value"), {"value": value})

    assert ledger.verify_chain()  # the events are untouched: the replay finds the change
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == ["REGISTRO ALTERATO", f"  {line}"]


def test_every_new_event_binds_the_state_it_leaves(ledger: Ledger) -> None:
    ticket = ledger.open(review())
    ledger.apply(ticket, Action.DELIVER, "qa-inspector", verdict=Verdict.READY, delivered=DELIVERED)
    ledger.add_evidence(
        EvidenceEntry(
            at="2026-11-09T10:00:00+00:00",
            project="default",
            file="segno.svg",
            sha256="a1b2",
            check_name="svg_audit",
            result="PASS",
            signer="qa-inspector",
            ticket_id=ticket,
        )
    )
    ledger.apply(ticket, Action.REWORK, "design-director", "rifai la verifica")

    (row,) = ledger.tickets("default")
    # What `open` fixes for good: the contract, the opening hashes and the project (ADR-0049, ADR-0053).
    contract = {
        "inputs_sha256": EMPTY_SHA256,
        "project": "default",
        "spec_sha256": chain.text_sha256(row.spec_json),
    }
    delivered = {"delivered": DELIVERED, "status": "delivered", "verdict": "READY"} | contract
    (proof_row,) = ledger.evidence("default")
    events = ledger.history(ticket)
    assert [(event.action, event.version, json.loads(event.payload_json)) for event in events] == [
        ("open", 2, {"delivered": {}, "status": "open", "verdict": None} | contract),
        ("deliver", 2, delivered),
        ("evidence", 2, delivered | {"evidence": proof_row.model_dump()}),
        ("rework", 2, {"delivered": DELIVERED, "status": "rework", "verdict": None} | contract),
    ]
    assert all(event.payload_json == chain.canonical(json.loads(event.payload_json)) for event in events)
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def test_an_event_without_a_ticket_binds_only_its_row(ledger: Ledger) -> None:
    ledger.add_evidence(
        EvidenceEntry(
            at="2026-11-09T10:00:00+00:00",
            project="default",
            file="segno.svg",
            sha256="a1b2",
            check_name="svg_audit",
            result="PASS",
            signer="qa-inspector",
        )
    )
    (row,) = ledger.evidence("default")
    assert [
        (event.action, event.version, json.loads(event.payload_json)) for event in ledger.history("-")
    ] == [("evidence", 2, {"evidence": row.model_dump()})]
    assert ledger.verify_chain()


def test_a_ticket_the_chain_does_not_bind_breaks_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ticket whose last event is version 1, or that has no event at all, has a state nothing in the chain
    vouches for."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ticket = ledger.open(production())
    with ledger.engine.begin() as conn:
        prev = conn.execute(text("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")).scalar_one()
        at = "2026-11-09T10:00:00+00:00"
        digest = chain.digest(prev, ticket, at, "identity-designer", "block", "manca il brief")
        conn.execute(
            text(
                "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash)"
                " VALUES (:ticket, :at, 'identity-designer', 'block', 'manca il brief', :prev, :hash)"
            ),
            {"ticket": ticket, "at": at, "prev": prev, "hash": digest},
        )
    with Session(ledger.engine) as session:
        session.add(
            TicketRow(
                id="T-0002",
                spec_json=production().model_dump_json(),
                status=Status.OPEN.value,
                created_at="2026-11-09T10:00:00+00:00",
            )
        )
        session.commit()

    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == [
        "T-0001: stato non legato alla catena",
        "T-0002: stato non legato alla catena",
    ]
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:3] == [
        "REGISTRO ALTERATO",
        "  T-0001: stato non legato alla catena",
        "  T-0002: stato non legato alla catena",
    ]


def test_a_version_1_event_binds_no_state_whatever_its_payload_says(ledger: Ledger) -> None:
    """A version-1 digest does not cover `payload_json`, so a payload written into a v1 row afterwards proves
    nothing, even when it matches the ticket row exactly."""
    ticket = ledger.open(production())
    (row,) = ledger.tickets("default")
    forged = chain.canonical(
        chain.ticket_binding(row.status, row.verdict, {}, row.spec_json, row.inputs_json, row.project)
    )
    with ledger.engine.begin() as conn:
        prev = conn.execute(text("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")).scalar_one()
        at = "2026-11-09T10:00:00+00:00"
        digest = chain.digest(prev, ticket, at, "identity-designer", "block", "manca il brief")
        conn.execute(
            text(
                "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash)"
                " VALUES (:ticket, :at, 'identity-designer', 'block', 'manca il brief', :prev, :hash)"
            ),
            {"ticket": ticket, "at": at, "prev": prev, "hash": digest},
        )
        conn.execute(text("DROP TRIGGER events_no_update"))
        conn.execute(
            text("UPDATE events SET payload_json = :forged WHERE hash = :hash"),
            {"forged": forged, "hash": digest},
        )

    last = ledger.history(ticket)[-1]
    assert (last.version, last.payload_json) == (1, forged)
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == [f"{ticket}: stato non legato alla catena"]


def test_a_version_1_event_binds_no_row_whatever_its_payload_says(ledger: Ledger) -> None:
    """A row written afterwards into the payload of a version-1 event vouches for nothing, since that digest
    does not cover `payload_json`: a gate inserted directly stays unbound (ADR-0049)."""
    ticket = ledger.open(production())
    forged = decision().model_dump() | {"seq": 1}
    with ledger.engine.begin() as conn:
        prev = conn.execute(text("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")).scalar_one()
        at = "2026-11-10T10:00:00+00:00"
        digest = chain.digest(prev, ticket, at, "identity-designer", "block", "")
        conn.execute(
            text(
                "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash)"
                " VALUES (:ticket, :at, 'identity-designer', 'block', '', :prev, :hash)"
            ),
            {"ticket": ticket, "at": at, "prev": prev, "hash": digest},
        )
        conn.execute(text("DROP TRIGGER events_no_update"))
        conn.execute(
            text("UPDATE events SET payload_json = :forged WHERE hash = :hash"),
            {"forged": chain.canonical({"gate": forged}), "hash": digest},
        )
        conn.execute(
            text(
                "INSERT INTO gates (seq, at, project, gate, approved, choice, text, files_json)"
                " VALUES (:seq, :at, :project, :gate, :approved, :choice, :text, :files_json)"
            ),
            forged,
        )

    assert ledger.verify_chain()
    assert "gate 1: riga non legata alla catena" in ledger.replay_mismatches()


@pytest.mark.parametrize(
    ("statement", "line"),
    [
        (
            "UPDATE tickets SET spec_json = replace(spec_json, 'master_open', 'svg_audit')",
            "T-0001: contratto diverso dalla catena",
        ),
        (
            """UPDATE tickets SET inputs_json = '{"brief.md": "c3d4"}'""",
            "T-0001: hash d'apertura diversi dalla catena",
        ),
    ],
)
def test_changing_a_ticket_contract_breaks_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    statement: str,
    line: str,
) -> None:
    """The contract decides who delivers and what a delivery needs, the opening hashes what is stale. Nothing
    changes them after `open`, and the chain binds their sha256 (2.F56, ADR-0049)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ledger.open(production(), inputs={"brief.md": "a1b2"})
    assert cli.main(["verify"]) == 0
    capsys.readouterr()

    with ledger.engine.begin() as conn:
        conn.execute(text(statement))

    assert ledger.verify_chain()  # the events are untouched: the replay finds the change
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == ["REGISTRO ALTERATO", f"  {line}"]


def test_moving_a_ticket_to_another_project_breaks_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ticket's project decides whose work folder its agents write and whose budget pays its calls. Nothing
    changes it after `open`, and the chain binds it (ADR-0053)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ledger.open(production(), project="merlo")
    assert cli.main(["verify"]) == 0
    capsys.readouterr()

    with ledger.engine.begin() as conn:
        conn.execute(text("UPDATE tickets SET project = 'merlo4'"))

    assert ledger.verify_chain()  # the events are untouched: the replay finds the change
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == [
        "REGISTRO ALTERATO",
        "  T-0001: progetto diverso dalla catena",
    ]


@pytest.mark.parametrize("next_event", ["block", "paid call"])
def test_a_moved_ticket_stays_caught_after_its_next_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], next_event: str
) -> None:
    """The ticket's next event binds the row as it finds it, moved project included: the first call its agents
    make in the other client's folder would hide the move. `agency verify` compares every event (ADR-0054)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    ticket = ledger.open(production(), project="merlo")
    with ledger.engine.begin() as conn:
        conn.execute(text("UPDATE tickets SET project = 'merlo4'"))

    if next_event == "block":
        ledger.apply(ticket, Action.BLOCK, "identity-designer", "manca il brief")
    else:
        # the gateway charges the project it reads from the moved row
        ledger.record_usage(paid(ticket).model_copy(update={"project": "merlo4"}))

    assert ledger.verify_chain()
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == [
        "REGISTRO ALTERATO",
        "  T-0001: progetto diverso dalla catena",
    ]


def idea(**extra: object) -> ConceptEntry:
    return ConceptEntry.model_validate(
        {"project": "default", "round": 1, "letter": "A", "lever": "forma", "idea_ticket": ""} | extra
    )


def decision() -> GateEntry:
    return GateEntry(
        at="2026-11-10T10:00:00+00:00",
        project="default",
        gate="concept",
        approved=True,
        choice="B",
        text="Va bene la B",
        files_json='{"presentazione.pdf": "a1b2"}',
    )


def proof(ticket: str) -> EvidenceEntry:
    return EvidenceEntry(
        at="2026-11-10T10:00:00+00:00",
        project="default",
        file="segno.svg",
        sha256="a1b2",
        check_name="svg_audit",
        result="FAIL",
        signer="qa-inspector",
        ticket_id=ticket,
    )


def test_a_concept_opened_with_its_ticket_starts_as_an_idea(ledger: Ledger) -> None:
    """The status a concept row stores before its sketch arrives."""
    ticket = ledger.open(production(), concept=idea())
    assert [(row.idea_ticket, row.status) for row in ledger.concepts("default", 1)] == [(ticket, "idea")]


FIXED_CLOCK = "2026-01-01T00:00:00+00:00"
# The newest event's hash when these values are written with a fixed clock. Copied from the output of the row
# API, before ADR-0058's entries replaced it: an entry must bind the same bytes into the chain.
CONCEPT_CHAIN_HEAD = "6e5134d679a59e24478e914126db7a9b11da5232cee3b64fdc729ec2c522ab2d"
GATE_CHAIN_HEAD = "9e94c4155636603f87cd9234afe0c1aa0ccfd81e47bd22f71b3d99159f6d21c0"
EVIDENCE_CHAIN_HEAD = "838c7014e948d5d7f95adadc64e213a7e793ff8f1cd5a652865b80860737a92f"
USAGE_CHAIN_HEAD = "49af0c7f6b1f2326e7de7e88fced8146aca9d9f68214ccfc19634f4a6bdfb2e1"


def newest_hash(ledger: Ledger) -> str:
    with Session(ledger.engine) as session:
        event = session.exec(select(EventRow).order_by(col(EventRow.seq).desc())).first()
    assert event is not None
    return event.hash


def test_the_sqlite_ledger_is_a_ledger_port(tmp_path: Path) -> None:
    """The engine reaches the registry through its ports (ADR-0058): pyright checks every method here."""
    port: LedgerPort = Ledger(tmp_path / "l.sqlite")
    assert port.tickets("default") == []


def test_a_concept_written_through_an_entry_chains_like_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agency.ledger.store.now", lambda: FIXED_CLOCK)
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.open(production(), concept=idea(anon="X"))
    assert ledger.verify_chain()
    assert newest_hash(ledger) == CONCEPT_CHAIN_HEAD


def test_a_gate_written_through_an_entry_chains_like_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agency.ledger.store.now", lambda: FIXED_CLOCK)
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.add_gate(decision())
    assert ledger.verify_chain()
    assert newest_hash(ledger) == GATE_CHAIN_HEAD


def test_evidence_written_through_an_entry_chains_like_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agency.ledger.store.now", lambda: FIXED_CLOCK)
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.add_evidence(proof(ledger.open(production())))
    assert ledger.verify_chain()
    assert newest_hash(ledger) == EVIDENCE_CHAIN_HEAD


def test_a_paid_call_written_through_an_entry_chains_like_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agency.ledger.store.now", lambda: FIXED_CLOCK)
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_usage(paid(ledger.open(production())))
    assert ledger.verify_chain()
    assert newest_hash(ledger) == USAGE_CHAIN_HEAD


def link() -> DerivationEntry:
    return DerivationEntry(
        at=FIXED_CLOCK,
        project="default",
        master="source/segno.vectorcraft",
        master_sha="m1",
        export="exports/segno.svg",
        export_sha="e1",
        how="export",
    )


def test_a_derivation_written_through_an_entry_is_stored_as_the_row(ledger: Ledger) -> None:
    """Derivations are not chained: what matters is the stored link, and that a replay adds nothing."""
    ledger.add_derivation(link())
    ledger.add_derivation(link())
    stored = ledger.derivations("default", "exports/segno.svg")
    assert [row.model_dump() for row in stored] == [link().model_dump() | {"seq": 1}]


def with_rows(ledger: Ledger) -> str:
    """An idea, the client's decision and a proof, written as the studio writes them."""
    ticket = ledger.open(production(), concept=idea())
    ledger.update_concept(ticket, status="selezionata", anon="B")
    ledger.add_gate(decision())
    ledger.add_evidence(proof(ticket))
    return ticket


@pytest.mark.parametrize(
    ("statements", "line"),
    [
        (["UPDATE concepts SET status = 'proposta'"], "idea 1: riga diversa dalla catena"),
        (["DELETE FROM concepts"], "idea 1: mancante nel registro"),
        (
            [
                "INSERT INTO concepts (project, round, letter, lever, anon, card_json, idea_ticket,"
                " sketch_ticket, sketch_file, status) VALUES ('default', 1, 'B', 'colore', 'A', '{}',"
                " 'T-0001', '', '', 'proposta')"
            ],
            "idea 2: riga non legata alla catena",
        ),
        (
            ["DROP TRIGGER gates_no_update", "UPDATE gates SET choice = 'A'"],
            "gate 1: riga diversa dalla catena",
        ),
        # the model reads 'no' back as True, the bound value: verify compares what is stored
        (
            ["DROP TRIGGER gates_no_update", "UPDATE gates SET approved = 'no'"],
            "gate 1: riga diversa dalla catena",
        ),
        (["DROP TRIGGER gates_no_delete", "DELETE FROM gates"], "gate 1: mancante nel registro"),
        (
            [
                "INSERT INTO gates (at, project, gate, approved, choice, text, files_json)"
                " VALUES ('2026-11-10T11:00:00+00:00', 'default', 'concept', 1, 'A', 'La A', '{}')"
            ],
            "gate 2: riga non legata alla catena",
        ),
        (
            ["DROP TRIGGER evidence_no_update", "UPDATE evidence SET result = 'PASS'"],
            "prova 1: riga diversa dalla catena",
        ),
        (["DROP TRIGGER evidence_no_delete", "DELETE FROM evidence"], "prova 1: mancante nel registro"),
        (
            [
                "INSERT INTO evidence (at, project, file, sha256, check_name, result, signer, ticket_id,"
                " proof, note, inputs_json) VALUES ('2026-11-10T11:00:00+00:00', 'default', 'segno.svg',"
                " 'a1b2', 'svg_parity', 'PASS', 'qa-inspector', 'T-0001', '', '', '{}')"
            ],
            "prova 2: riga non legata alla catena",
        ),
    ],
)
def test_changing_an_idea_a_gate_or_a_proof_breaks_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    statements: list[str],
    line: str,
) -> None:
    """Ideas decide what is developed and presented, gates hold the client's decisions, proofs decide whether
    a delivery passes. The triggers of gates and evidence are one DROP TRIGGER away, and concepts have none:
    each row is bound into the chain, and verify compares the table with it (2.F57, 2.F58, ADR-0049)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    with_rows(ledger)
    assert cli.main(["verify"]) == 0
    capsys.readouterr()

    with ledger.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

    assert ledger.verify_chain()  # the events are untouched: the replay finds the change
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == ["REGISTRO ALTERATO", f"  {line}"]


def test_deleting_a_ticket_breaks_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tickets` has no triggers: a row deleted outright leaves the events that bind its state in the chain,
    and verify reports the ticket as missing."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    with_rows(ledger)
    ledger.open(production())
    assert cli.main(["verify"]) == 0
    capsys.readouterr()

    with ledger.engine.begin() as conn:
        conn.execute(text("DELETE FROM tickets WHERE id = 'T-0001'"))

    assert ledger.verify_chain()
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:3] == [
        "REGISTRO ALTERATO",
        "  T-0001: ticket mancante nel registro",
        "artefatti integri: 0",
    ]


def test_a_proof_for_an_id_without_a_ticket_is_no_missing_ticket(ledger: Ledger) -> None:
    """Only an event that binds a ticket's state vouches that the ticket existed: a proof recorded for an id
    with no ticket row binds no state, and is not a deleted ticket."""
    ledger.add_evidence(proof("T-0042"))
    assert ledger.history("T-0042")[0].action == "evidence"
    assert ledger.replay_mismatches() == []


def test_a_version_1_payload_vouches_for_no_ticket(ledger: Ledger) -> None:
    """A state written afterwards into the payload of a version-1 event is not covered by its digest: the
    ticket it names never had to exist, so it is not reported as missing."""
    ledger.open(production())
    forged = chain.canonical({"delivered": {}, "status": "open", "verdict": None})
    with ledger.engine.begin() as conn:
        prev = conn.execute(text("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")).scalar_one()
        at = "2026-11-10T10:00:00+00:00"
        digest = chain.digest(prev, "T-0099", at, "identity-designer", "block", "")
        conn.execute(
            text(
                "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, payload_json)"
                " VALUES ('T-0099', :at, 'identity-designer', 'block', '', :prev, :hash, :forged)"
            ),
            {"at": at, "prev": prev, "hash": digest, "forged": forged},
        )

    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def test_every_idea_and_gate_write_binds_the_row(ledger: Ledger) -> None:
    """Each write of an idea or a gate appends an event that binds the whole row as it leaves it, outside the
    history of any ticket (ADR-0049)."""
    ticket = with_rows(ledger)
    other = ledger.open(production(), concept=idea(letter="B"))

    first = idea(seq=1, idea_ticket=ticket).model_dump()
    chosen = first | {"status": "selezionata", "anon": "B"}
    second = first | {"seq": 2, "letter": "B", "idea_ticket": other}
    gate = decision().model_dump() | {"seq": 1}
    assert [(e.actor, e.action, e.version, json.loads(e.payload_json)) for e in ledger.history("-")] == [
        ("harness", "concept", 2, {"concept": first}),
        ("harness", "concept", 2, {"concept": chosen}),
        ("harness", "gate", 2, {"gate": gate}),
        ("harness", "concept", 2, {"concept": second}),
    ]
    assert [event.action for event in ledger.history(ticket)] == ["open", "evidence"]
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def paid(ticket: str, cost: float = 0.25) -> UsageEntry:
    return UsageEntry(
        at="2026-11-10T10:00:00+00:00",
        project="default",
        ticket_id=ticket,
        role="identity-designer",
        instance="i",
        model="claude-opus-5-5",
        input_tokens=1200,
        output_tokens=300,
        cost_usd=cost,
        stop_reason="tool_use",
        request_id="req_1",
        run=1,
        phase="identity",
        effort="high",
        duration_ms=900,
        ttft_ms=200,
    )


def with_costs(ledger: Ledger) -> str:
    """A project with its budget, a ticket and a paid call, written as the studio writes them."""
    ledger.set_project("default", 30.0)
    ticket = ledger.open(production())
    ledger.record_usage(paid(ticket))
    return ticket


@pytest.mark.parametrize(
    ("statements", "line"),
    [
        (
            ["DROP TRIGGER usage_no_update", "UPDATE usage SET cost_usd = 0.01"],
            "consumo 1: riga diversa dalla catena",
        ),
        (["DROP TRIGGER usage_no_delete", "DELETE FROM usage"], "consumo 1: mancante nel registro"),
        (
            [
                "INSERT INTO usage (at, project, ticket_id, role, instance, model, input_tokens,"
                " output_tokens, cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cost_usd,"
                " stop_reason, request_id) VALUES ('2026-11-10T11:00:00+00:00', 'default', 'T-0001',"
                " 'identity-designer', 'i', 'claude-opus-5-5', 10, 10, 0, 0, 0, 0.5, 'end_turn', 'req_2')"
            ],
            "consumo 2: riga non legata alla catena",
        ),
        (["UPDATE projects SET budget_usd = 300"], "progetto default: riga diversa dalla catena"),
        (["DELETE FROM projects"], "progetto default: mancante nel registro"),
        (
            ["INSERT INTO projects (name, budget_usd, model, effort) VALUES ('altro', 5, '', '')"],
            "progetto altro: riga non legata alla catena",
        ),
        # projects are named, and reported, in name order
        (
            [
                "INSERT INTO projects (name, budget_usd, model, effort) VALUES ('zeta', 5, '', '')",
                "INSERT INTO projects (name, budget_usd, model, effort) VALUES ('beta', 5, '', '')",
            ],
            "progetto beta: riga non legata alla catena",
        ),
    ],
)
def test_changing_a_cost_or_a_budget_breaks_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    statements: list[str],
    line: str,
) -> None:
    """`usage` feeds what a project has spent, `projects` holds its budget: together they decide whether a
    call is paid for. The triggers of usage are one DROP TRIGGER away, and projects have none: each row is
    bound into the chain, and verify compares the table with it (2.F65, ADR-0050)."""
    ledger = Ledger(use_data_dir(tmp_path, monkeypatch))
    with_costs(ledger)
    assert cli.main(["verify"]) == 0
    capsys.readouterr()

    with ledger.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

    assert ledger.verify_chain()  # the events are untouched: the replay finds the change
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines()[:2] == ["REGISTRO ALTERATO", f"  {line}"]


def test_every_cost_and_budget_write_binds_the_row(ledger: Ledger) -> None:
    """A paid call binds its row on its ticket, with the ticket's state, as a proof does; a call outside a
    ticket, and every write of a project, bind theirs outside any ticket's history (ADR-0050)."""
    ticket = with_costs(ledger)
    ledger.record_usage(paid(""))
    ledger.set_budget("default", 45.0)
    ledger.set_project("default", 50.0, "claude-sonnet-5-5", "low")

    (row,) = ledger.tickets("default")
    state = chain.ticket_binding(row.status, row.verdict, {}, row.spec_json, row.inputs_json, row.project)
    first, second = ledger.usage("default")
    project = {"name": "default", "budget_usd": 30.0, "model": "", "effort": ""}
    chosen = {"name": "default", "budget_usd": 50.0, "model": "claude-sonnet-5-5", "effort": "low"}
    assert [(e.actor, e.action, e.version, json.loads(e.payload_json)) for e in ledger.history("-")] == [
        ("harness", "project", 2, {"project": project}),
        ("harness", "usage", 2, {"usage": second.model_dump()}),
        ("harness", "project", 2, {"project": project | {"budget_usd": 45.0}}),
        ("harness", "project", 2, {"project": chosen}),
    ]
    assert [(e.actor, e.action, json.loads(e.payload_json)) for e in ledger.history(ticket)] == [
        ("design-director", "open", state),
        ("harness", "usage", state | {"usage": first.model_dump()}),
    ]
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def test_parallel_paid_calls_each_bind_their_row(tmp_path: Path) -> None:
    """Explorers call the model from parallel threads, and two processes can write at once: every paid call
    gets its own event, in the order of the rows, on one unbroken chain."""
    path = tmp_path / "ledger.sqlite"
    writers = [Ledger(path), Ledger(path)]  # no lock shared in memory between the two, as between processes
    ticket = writers[0].open(production())
    start = threading.Barrier(8)
    errors: list[Exception] = []

    def calls(ledger: Ledger, worker: int) -> None:
        start.wait()
        try:
            for n in range(10):
                ledger.record_usage(paid(ticket, cost=worker + n / 100))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=calls, args=(writers[n % 2], n)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    rows = writers[0].usage("default")
    assert len(rows) == 80
    events = [event for event in writers[0].history(ticket) if event.action == "usage"]
    assert [json.loads(event.payload_json)["usage"]["seq"] for event in events] == [row.seq for row in rows]
    assert writers[0].verify_chain()
    assert writers[0].replay_mismatches() == []


@pytest.mark.parametrize("paused", ["set_budget", "set_project"])
def test_a_project_write_binds_the_row_it_leaves_while_another_writes(tmp_path: Path, paused: str) -> None:
    """`set_budget` and `set_project` read the project before they write it. A write from another process in
    between would leave its change in the table and the row read before in the chain: each write holds the
    chain's lock from its read to its commit (ADR-0050)."""
    path = tmp_path / "ledger.sqlite"
    first, other = Ledger(path), Ledger(path)  # no lock shared in memory, as between two processes
    first.set_project("default", 30.0)
    read, written = threading.Event(), threading.Event()

    @sa_event.listens_for(first.engine, "after_cursor_execute")
    def pause(_conn: object, _cursor: object, statement: str, *_: object) -> None:
        if statement.startswith("SELECT") and "FROM projects" in statement and not read.is_set():
            read.set()
            written.wait(1)  # the other write lands now, unless this one holds the lock

    def write_other() -> None:
        read.wait()
        other.set_project("default", 30.0, "claude-sonnet-5-5", "low")
        written.set()

    thread = threading.Thread(target=write_other)
    thread.start()
    if paused == "set_budget":
        first.set_budget("default", 45.0)
    else:
        first.set_project("default", 50.0)
    thread.join()

    assert first.replay_mismatches() == []
    assert first.verify_chain()


def test_a_binding_names_its_row_only_with_a_value_of_the_column_type(ledger: Ledger) -> None:
    """A paid call is named by its seq, a number, and a project by its name, a text: a binding that names its
    row with another type names no row of the table, and no row is reported lost for it."""
    with_costs(ledger)
    (call,) = ledger.usage("default")
    forged = [
        {"usage": call.model_dump() | {"seq": "1"}},
        {"project": {"name": 7, "budget_usd": 30.0, "model": "", "effort": ""}},
    ]
    with ledger.engine.begin() as conn:
        for binding in forged:
            prev = conn.execute(text("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")).scalar_one()
            at, payload = "2026-11-10T10:00:00+00:00", chain.canonical(binding)
            conn.execute(
                text(
                    "INSERT INTO events (ticket_id, at, actor, action, note, prev_hash, hash, version,"
                    " payload_json) VALUES ('-', :at, 'harness', 'usage', '', :prev, :hash, 2, :payload)"
                ),
                {
                    "at": at,
                    "prev": prev,
                    "hash": chain.digest_v2(prev, "-", at, "harness", "usage", "", payload),
                    "payload": payload,
                },
            )

    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def test_resume_records_cannot_be_rewritten(ledger: Ledger) -> None:
    """A resume record says that an effect already happened: changing or deleting it would repeat the effect
    or skip it (2.F65, ADR-0050)."""
    ledger.record_operation("i:t1", "i", "view_image", '{"key": "a.png:a1b2"}')
    with ledger.engine.begin() as conn, pytest.raises(Exception, match="solo in aggiunta"):
        conn.execute(text("UPDATE operations SET result_json = '{}'"))
    with ledger.engine.begin() as conn, pytest.raises(Exception, match="solo in aggiunta"):
        conn.execute(text("DELETE FROM operations"))
    assert ledger.operation("i:t1") == '{"key": "a.png:a1b2"}'


def test_a_repeated_operation_keeps_its_first_record(ledger: Ledger) -> None:
    ledger.record_operation("i:t1", "i", "view_image", '{"key": "a.png:a1b2"}')
    first = [row.model_dump() for row in ledger.operations("i")]

    ledger.record_operation("i:t1", "i", "view_image", '{"key": "a.png:c3d4"}')

    assert [row.model_dump() for row in ledger.operations("i")] == first


def test_a_replayed_view_image_shows_the_image_and_keeps_the_first_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A turn interrupted after its view_image ran, by a later tool of the same turn, is replayed with the
    same tool_use ids. view_image returns no stored result (effect=False): it runs again and records again.
    The model gets the image, and the record stays the first one (ADR-0050)."""
    ticks = itertools.count()
    monkeypatch.setattr(store, "now", lambda: f"2026-11-10T10:00:{next(ticks):02d}+00:00")
    work = tmp_path / "work"
    work.mkdir()
    Image.new("RGB", (40, 40), (200, 0, 0)).save(work / "a.png")
    ledger = Ledger(tmp_path / "ledger.sqlite")
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    toolbox = Toolbox(context)
    first = toolbox.call("t1", "view_image", {"path": "a.png"})
    record = [row.model_dump() for row in ledger.operations("i")]

    replay = toolbox.call("t1", "view_image", {"path": "a.png"})

    assert "is_error" not in replay
    assert [block["type"] for block in replay["content"]] == ["image", "text"]
    assert replay["content"][0] == first["content"][0]
    assert [row.model_dump() for row in ledger.operations("i")] == record


def test_verify_on_a_missing_registry_exits_1_with_its_path_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = use_data_dir(tmp_path, monkeypatch)
    assert not path.exists()
    assert cli.main(["verify"]) == 1
    assert capsys.readouterr().out.splitlines() == [f"REGISTRO: nessun registro in {path.absolute()}"]
    assert not path.exists()


def test_past_projects_stay_readable() -> None:
    old = {
        "title": "Idea A",
        "request": "r",
        "type": "idea",
        "sender": "design-director",
        "assignee": "direction-a",
        "outputs": ["scheda.json"],
        "max_tools": 16,  # a field from an earlier version
    }
    assert TicketSpec.model_validate(old).type is TicketType.IDEA


def test_ticket_10000_sorts_after_ticket_9999(ledger: Ledger) -> None:
    with Session(ledger.engine) as session:
        session.add_all(
            TicketRow(
                id=f"T-{n:04d}",
                project="merlo4",
                spec_json=production().model_dump_json(),
                status=Status.OPEN.value,
                created_at="2026-11-02T09:00:00+00:00",
            )
            for n in range(1, 9999)
        )
        session.commit()
    parent = "T-0001"
    first = ledger.open(production(parent=parent), "merlo4")
    second = ledger.open(production(parent=parent), "merlo4")

    assert (first, second) == ("T-9999", "T-10000")
    assert [row.id for row in ledger.tickets("merlo4")][-2:] == [first, second]
    assert ledger.children(parent) == [first, second]
