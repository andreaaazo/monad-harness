"""The final gate with real Craft and recorded answers: the client's words send the work back."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agency.process.session import open_session
from support.scripted import turn
from support.settings import settings
from support.sketch import BUDGET, CHECKS, OUTPUTS, Router, brief, full_script, use

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


def test_client_refusing_the_final_work_sends_it_back_with_their_words(tmp_path: Path) -> None:
    script = full_script()
    script["T-0001"].append(turn(use("block", reason="aspetto il nuovo segno")))
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    assert session.pending("officina")[0].gate == "final"

    outcome = session.decide("officina", False, "Il tratto è troppo sottile")

    rework = [event for event in session.ledger.history("T-0001") if event.action == "rework"]
    assert [event.note for event in rework] == ["Il tratto è troppo sottile"]
    assert outcome == "bloccato: aspetto il nuovo segno"
