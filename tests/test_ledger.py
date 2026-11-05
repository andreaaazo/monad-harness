from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from agency import cli
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType, Verdict
from agency.ledger import ForbiddenAction, IllegalTransition, Ledger


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


def test_verify_on_a_missing_registry_creates_one_and_calls_it_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Pins current behavior of DX-003; phase 2 (Task 2.14) flips these assertions.
    path = use_data_dir(tmp_path, monkeypatch)
    assert not path.exists()
    assert cli.main(["verify"]) == 0
    assert capsys.readouterr().out.splitlines() == ["registro integro", "artefatti integri: 0"]
    assert path.is_file()


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
