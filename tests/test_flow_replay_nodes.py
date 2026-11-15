"""Graph nodes on resume: a node run again writes nothing it has already written."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from PIL import Image

from agency.contracts.concept import ConceptCard
from agency.contracts.ledger import ConceptEntry
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import ProjectName, parse_project_name
from agency.contracts.ticket import Action
from agency.ledger import Ledger
from agency.process import graph as workflow
from agency.studio.presentation import document
from support.flow import DIRECTOR, closing_box, crash_after_the_transition, intact, production_spec
from support.rules import RULES
from support.settings import settings

CARD = ConceptCard(
    concept="Il merlo",
    client_fact="Fatto",
    why_not_obvious="Non ovvia",
    drawing="Un merlo",
    substitution="Solo lui",
).model_dump_json()


class Proposals:
    """A project at the proposals node: one selected idea, its sketch, the brief and the applications."""

    def __init__(self, tmp_path: Path) -> None:
        self.settings = settings(tmp_path)
        self.ledger = Ledger(tmp_path / "l.sqlite")
        self.runner = MagicMock()
        self.runner.run.return_value = Outcome(state=OutcomeState.BLOCKED, note="fermo")
        self.graph = workflow.build(self.runner, self.ledger, self.settings, InMemorySaver(), rules=RULES)
        self.work = self.settings.project_dir(parse_project_name("p")) / "work"
        folder = self.work / "explorations/r1"
        (folder / "a").mkdir(parents=True)
        (self.work / "brief.md").write_text("brief")
        (folder / "a/scheda.json").write_text("{}")
        Image.new("RGB", (8, 8), (20, 20, 20)).save(folder / "a/schizzo-a.png")
        (folder / "applicazioni.json").write_text(json.dumps([{"name": "timbro", "size": "16 mm"}]))
        self.root = self.ledger.open(production_spec(), "p")
        idea = production_spec().model_copy(update={"title": "Idea", "assignee": "direction-a"})
        row = ConceptEntry(
            project="p",
            round=1,
            letter="a",
            lever="il nome",
            idea_ticket="",
            anon="Z",
            card_json=CARD,
            status="selezionata",
            sketch_file="explorations/r1/a/schizzo-a.png",
        )
        self.idea = self.ledger.open(idea, "p", concept=row)

    def run(self, node: str) -> None:
        state = {"project": "p", "root": self.root, "exploration": 1, "client_note": "", "chosen": "Z"}
        self.graph.nodes[node].bound.func(state)  # type: ignore[attr-defined]

    def prepare(self) -> None:
        self.run("prepare_proposals")

    def concept_events(self) -> int:
        return sum(event.action == "concept" for event in self.ledger.history("-"))

    def status(self) -> str:
        (row,) = self.ledger.concepts("p", 1)
        return row.status

    def proposals(self) -> list[str]:
        return [t for t in self.ledger.children(self.root) if "Proposta" in self.ledger.spec(t).title]


def test_a_replayed_proposals_node_still_sets_the_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Proposals(tmp_path)

    def die(*_: object, **__: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(studio.ledger, "update_concept", die)
        with pytest.raises(KeyboardInterrupt):
            studio.prepare()
    assert len(studio.proposals()) == 1
    assert studio.status() == "selezionata"  # the process died between the ticket and the status

    studio.prepare()

    assert len(studio.proposals()) == 1  # the ticket is not opened twice
    assert studio.status() == "in-sviluppo"
    intact(studio.ledger)


def test_a_replayed_present_node_appends_no_second_concept_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Proposals(tmp_path)
    studio.prepare()
    (proposal,) = studio.proposals()
    studio.ledger.apply(proposal, Action.DELIVER, "identity-designer", "fatto", None, {})
    monkeypatch.setattr(document, "proposal_files", lambda *_: (Path("mark.png"), ()))
    monkeypatch.setattr(document, "sheet", lambda *_: None)
    studio.run("present")
    assert studio.status() == "proposta"
    events = studio.concept_events()

    studio.run("present")  # the node ran again after a crash

    assert studio.status() == "proposta"
    assert studio.concept_events() == events
    intact(studio.ledger)


def test_a_replayed_select_concepts_appends_no_second_concept_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, context, _ = closing_box(tmp_path, DIRECTOR, "design-director", "select_concepts")
    context.settings = settings(tmp_path)
    context.round = 1
    row = ConceptEntry(
        project="p", round=1, letter="a", lever="il nome", idea_ticket="", anon="Z", card_json=CARD
    )
    context.ledger.open(production_spec(), "p", concept=row)
    ratings = context.settings.layout.ratings(ProjectName("p"), 1)
    ratings.parent.mkdir(parents=True, exist_ok=True)
    ratings.write_text(json.dumps([{"letter": "Z", "passes": True}]))
    arguments = {"chosen": ["Z"], "reasons": "regge"}
    crash_after_the_transition(box, context, monkeypatch, "select_concepts", arguments)
    events = sum(event.action == "concept" for event in context.ledger.history("-"))

    result = box.call("t1", "select_concepts", arguments)

    assert not result.get("is_error"), result["content"]
    assert [r.status for r in context.ledger.concepts("p", 1)] == ["selezionata"]
    assert sum(event.action == "concept" for event in context.ledger.history("-")) == events
    intact(context.ledger)


def test_update_concept_writes_only_a_change(tmp_path: Path) -> None:
    ledger = Ledger(settings(tmp_path).layout.ledger)
    row = ConceptEntry(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="Z", card_json=CARD)
    ticket = ledger.open(production_spec(), "p", concept=row)

    def events() -> int:
        return len(ledger.history("-"))

    before = events()

    ledger.update_concept(ticket, status="schizzo", lever="l")  # one field changes: a write
    assert events() == before + 1
    ledger.update_concept(ticket, status="schizzo", lever="l")
    ledger.update_concept(ticket, lever="l")
    assert events() == before + 1
    ledger.update_concept(ticket, status="schizzo", lever="altra")  # the second field changes: a write
    assert events() == before + 2
    assert ledger.concepts("p", 1)[0].lever == "altra"
    intact(ledger)


def test_a_node_run_once_sets_the_status_and_a_rerun_writes_nothing(tmp_path: Path) -> None:
    studio = Proposals(tmp_path)
    studio.prepare()
    assert studio.status() == "in-sviluppo"
    events = len(studio.ledger.history("-"))

    studio.prepare()

    assert len(studio.ledger.history("-")) == events  # an idea already in development writes no chain event
    assert len(studio.proposals()) == 1
