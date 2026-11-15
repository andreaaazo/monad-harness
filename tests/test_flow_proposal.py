"""The proposals with real Craft and recorded answers: developed in parallel, dropped or sent back."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest

from agency.process.session import open_session
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    OUTPUTS,
    Router,
    brief,
    options,
    plan_turn,
    present_turn,
    to_the_gate,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_proposals_run_in_parallel(tmp_path: Path) -> None:
    together = threading.Barrier(2, timeout=20)

    class Meeting(Router):
        def stream(self, params: dict) -> dict:
            key = self.key(params)
            if key in ("T-0006", "T-0007") and not self.requests[key]:
                together.wait()
            return super().stream(params)

    session = open_session(settings(tmp_path), Meeting(to_the_gate()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    spec = session.ledger.spec("T-0006")
    assert "timbro: 16 mm" in spec.request
    assert spec.workspace == "proposals/r1/x"


def test_studio_can_drop_a_proposal_before_the_client(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0001:present"] = present_turn("Y")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert options(session, "officina") == ["Y"]


def test_failed_proposal_does_not_stop_the_other(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0006"] = [turn(use("block", reason="Non regge alle dimensioni richieste"))]
    script["T-0001:present"] = present_turn("Y")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert options(session, "officina") == ["Y"]


def test_weak_proposals_go_back_to_exploration(tmp_path: Path) -> None:
    script = to_the_gate()
    empty = {"proposals": [], "recommended": None, "reasons": "Nessuna è presentabile"}
    script["T-0001:present"] = [turn(use("draft_presentation", **empty))]
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert session.pending("officina") == []
    assert "Nessuna è presentabile" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]
