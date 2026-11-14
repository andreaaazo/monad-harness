"""How each tool closes its instance when a resume replays it from the ledger (ADR-0057).

A tool already run is not run again on resume: its stored result comes back, and the tool itself says how
that result closes the instance. `test_restore_closes_each_closing_tool_with_its_state` in test_agent_flow.py
plays the same replays through `Toolbox.call`.
"""

from __future__ import annotations

from agency.agents.toolbox import TOOLS, PresentConcepts, ProposalText, SelectConcepts
from agency.contracts.outcome import Outcome, OutcomeState

CLOSING = {
    "deliver": OutcomeState.DELIVERED,
    "block": OutcomeState.BLOCKED,
    "hand_off": OutcomeState.HANDED_OFF,
    "plan_exploration": OutcomeState.HANDED_OFF,
    "submit_concept": OutcomeState.DELIVERED,
    "reject_concept": OutcomeState.CONCEPT_REJECTED,
}
REPLAYED = {"select_concepts", "draft_presentation", "present_concepts"}


def closed(name: str, stored: str) -> Outcome:
    """The outcome a tool closes with when its stored result is replayed."""
    replay = TOOLS[name].on_replay
    assert replay is not None
    outcome = replay(stored)
    assert outcome is not None
    return outcome


def test_the_closing_tools_keep_their_outcomes() -> None:
    assert {n: t.closes for n, t in TOOLS.items() if t.closes is not None} == CLOSING


def test_only_the_three_choice_tools_derive_their_outcome_from_the_stored_result() -> None:
    assert {n for n, t in TOOLS.items() if t.on_replay is not None} == REPLAYED


def test_a_replayed_selection_closes_by_what_it_chose() -> None:
    chose = SelectConcepts(chosen=["A"], reasons="r").model_dump_json()
    none = SelectConcepts(chosen=[], reasons="r").model_dump_json()
    assert closed("select_concepts", chose).state is OutcomeState.SELECTED
    assert closed("select_concepts", none).state is OutcomeState.NO_CONCEPT


def test_a_replayed_draft_closes_only_when_no_proposal_holds_up() -> None:
    replay = TOOLS["draft_presentation"].on_replay
    assert replay is not None
    assert replay('{"pagine": ["p.png"]}') is None
    assert closed("draft_presentation", '{"ok": true}').state is OutcomeState.NO_CONCEPT


def test_a_replayed_presentation_closes_by_its_proposals() -> None:
    empty = PresentConcepts(proposals=[], recommended=None, reasons="r").model_dump_json()
    one = PresentConcepts(
        proposals=[ProposalText(letter="A", title="t", idea="i", why="w", risk="r")],
        recommended="A",
        reasons="r",
    ).model_dump_json()
    assert closed("present_concepts", empty).state is OutcomeState.NO_CONCEPT
    assert closed("present_concepts", one).state is OutcomeState.PRESENTED
