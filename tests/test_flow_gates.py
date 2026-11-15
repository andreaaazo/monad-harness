"""A whole project with recorded answers and real Craft, from the brief to the client's final gate."""

from __future__ import annotations

from pathlib import Path

from agency.contracts.ticket import Status, Verdict
from agency.process.session import open_session
from support.flow import needs_craft, steps, use
from support.scripted import ScriptedTransport, turn
from support.settings import settings


@needs_craft
def test_full_project_reaches_the_client_gate_and_is_approved(tmp_path: Path) -> None:
    config = settings(tmp_path)
    brief = tmp_path / "brief.txt"
    brief.write_text("Un segno per un forno di quartiere")
    master, svg = "source/segno.vectorcraft", "exports/segno.svg"
    production = {
        "title": "Segno",
        "request": "Il segno del forno",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": [master, svg, "construction.md"],
        "checks": {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity"]},
        "media": ["vettoriale"],
        "exempt": {"construction.md": "documento di costruzione del segno"},
    }
    qa = {
        "title": "QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [svg],
        "checks": {"*.svg": ["svg_audit"]},
    }
    review = {
        "title": "Critica",
        "request": "Giudica",
        "type": "revisione",
        "assignee": "critic",
        "outputs": [svg],
        "checks": {"*.svg": ["critique"]},
    }
    proof = "proofs/render/exports_segno.svg.png"
    why = (
        "Rispetto alla versione precedente il segno ha un'apertura più netta e regge meglio a piccola scala."
    )
    script = [
        turn(use("open_ticket", "d1", **production)),
        turn(use("hand_off", "d2", note="attendo il segno")),
        turn(use("craft_run", "p1", document=master, steps=steps())),
        turn(use("export_master", "p2", master=master, output=svg)),
        turn(use("compute", "p3", code="print(1)")),
        turn(use("write_file", "p4", path="construction.md", content="unità u")),
        turn(use("write_file", "p5", path="source/precedente.md", content="v0")),
        turn(
            use("run_check", "p6", check="master_open", file=master),
            use("run_check", "p7", check="svg_audit", file=svg),
            use("run_check", "p8", check="svg_parity", file=svg),
        ),
        turn(use("deliver", "p9", note="segno pronto", verdict=None)),
        turn(use("open_ticket", "d3", **qa), use("open_ticket", "d4", **review)),
        turn(use("hand_off", "d5", note="attendo le revisioni")),
        turn(use("run_check", "q1", check="svg_audit", file=svg)),
        turn(use("deliver", "q2", note="tutto regolare", verdict="READY")),
        turn(use("render", "c1", path=svg)),
        turn(use("view_image", "c2", path=proof)),
        turn(
            use(
                "judge",
                "c3",
                file=svg,
                compare=["source/precedente.md"],
                why=why,
                result="PASS",
            )
        ),
        turn(use("deliver", "c4", note="regge", verdict="READY")),
        turn(
            use("accept_ticket", "d6", ticket="T-0002"),
            use("accept_ticket", "d7", ticket="T-0003"),
            use("accept_ticket", "d8", ticket="T-0004"),
        ),
        turn(use("deliver", "d9", note="consegnato", verdict=None)),
    ]
    transport = ScriptedTransport(script)
    session = open_session(config, transport)
    outputs = [master, svg, "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    session.start("forno", brief, outputs, checks, budget=1000.0, explore=False)
    assert session.pending("forno")[0].gate == "final"
    assert session.ledger.status("T-0001")[0] is Status.DELIVERED
    assert session.ledger.status("T-0003") == (Status.ACCEPTED, Verdict.READY)
    session.decide("forno", True, "va bene così")
    assert session.ledger.status("T-0001")[0] is Status.ACCEPTED
    assert session.pending("forno") == []
    assert session.ledger.verify_chain()
    critique = next(r for r in session.ledger.evidence("forno") if r.check_name == "critique")
    assert critique.signer == "critic"
    assert session.ledger.spent("forno") > 0


@needs_craft
def test_client_approval_of_a_root_without_critique_goes_back_to_rework(tmp_path: Path) -> None:
    """The client gate is the last system check: approving a root nobody critiqued sends it back (TST-002)."""
    config = settings(tmp_path)
    brief = tmp_path / "brief.txt"
    brief.write_text("Un segno per un forno di quartiere")
    master, svg = "source/segno.vectorcraft", "exports/segno.svg"
    production = {
        "title": "Segno",
        "request": "Il segno del forno",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": [master, svg, "construction.md"],
        "checks": {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity"]},
        "media": ["vettoriale"],
        "exempt": {"construction.md": "documento di costruzione del segno"},
    }
    qa = {
        "title": "QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [svg],
        "checks": {"*.svg": ["svg_audit"]},
    }
    script = [
        turn(use("open_ticket", "d1", **production)),
        turn(use("hand_off", "d2", note="attendo il segno")),
        turn(use("craft_run", "p1", document=master, steps=steps())),
        turn(use("export_master", "p2", master=master, output=svg)),
        turn(use("write_file", "p3", path="construction.md", content="unità u")),
        turn(
            use("run_check", "p4", check="master_open", file=master),
            use("run_check", "p5", check="svg_audit", file=svg),
            use("run_check", "p6", check="svg_parity", file=svg),
        ),
        turn(use("deliver", "p7", note="segno pronto", verdict=None)),
        turn(use("open_ticket", "d3", **qa)),
        turn(use("hand_off", "d4", note="attendo il QA")),
        turn(use("run_check", "q1", check="svg_audit", file=svg)),
        turn(use("deliver", "q2", note="tutto regolare", verdict="READY")),
        turn(use("accept_ticket", "d5", ticket="T-0002"), use("accept_ticket", "d6", ticket="T-0003")),
        turn(use("deliver", "d7", note="consegnato senza critica", verdict=None)),
        turn(use("block", "d8", reason="manca la critica del segno")),
    ]
    session = open_session(config, ScriptedTransport(script))
    outputs = [master, svg, "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    session.start("forno", brief, outputs, checks, budget=1000.0, explore=False)
    assert session.pending("forno")[0].gate == "final"
    session.decide("forno", True, "va bene così")
    rework = [event for event in session.ledger.history("T-0001") if event.action == "rework"]
    assert len(rework) == 1
    assert rework[0].actor == "router"
    assert rework[0].note.startswith("Accettazione rifiutata dal sistema:")
    assert f"{svg}: manca la prova 'critique'" in rework[0].note
    assert session.ledger.status("T-0001")[0] is not Status.ACCEPTED
