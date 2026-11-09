from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlmodel import Session

from agency import cli
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType, Verdict
from agency.ledger import ForbiddenAction, IllegalTransition, Ledger, chain
from agency.ledger.models import EvidenceRow, TicketRow


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
        EvidenceRow(
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

    delivered = '{"delivered":{"segno.svg":"a1b2"},"status":"delivered","verdict":"READY"}'
    assert [(event.action, event.version, event.payload_json) for event in ledger.history(ticket)] == [
        ("open", 2, '{"delivered":{},"status":"open","verdict":null}'),
        ("deliver", 2, delivered),
        ("evidence", 2, delivered),
        ("rework", 2, '{"delivered":{"segno.svg":"a1b2"},"status":"rework","verdict":null}'),
    ]
    assert ledger.verify_chain()
    assert ledger.replay_mismatches() == []


def test_an_event_without_a_ticket_binds_no_state(ledger: Ledger) -> None:
    ledger.add_evidence(
        EvidenceRow(
            at="2026-11-09T10:00:00+00:00",
            project="default",
            file="segno.svg",
            sha256="a1b2",
            check_name="svg_audit",
            result="PASS",
            signer="qa-inspector",
        )
    )
    assert [(event.action, event.version, event.payload_json) for event in ledger.history("-")] == [
        ("evidence", 2, "")
    ]
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
    status, verdict = ledger.status(ticket)
    forged = chain.ticket_state(status.value, verdict, ledger.delivered(ticket))
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
        "max_tools": 16,  # campo di una versione precedente
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
