"""The studio's process: first the idea is found, then it is built.

inside the studio: explorers who think by drawing, in parallel → anonymous board → the critic's first
look → choice of ideas → proposals in parallel
in front of the client: presentation → `concept` gate → finishing → revisions → `final` gate

The graph knows where the work is; the registry knows what happened. On resume a node runs again from the
start: finished work is not repeated, because each instance has a stable name and its own transcript.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send, interrupt

from agency.agents.loop import AgentRunner
from agency.config import Settings
from agency.contracts.concept import ConceptCard, ConceptStatus
from agency.contracts.gate import ConceptGate, Decision, FinalGate
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import RUNNABLE, Action, Medium, Status, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.ledger.models import GateRow
from agency.ledger.store import now
from agency.qa import delivery
from agency.studio.presentation.tools import PresentConcepts
from agency.studio.selection.tools import SelectConcepts
from agency.workshop import board, presentation
from agency.workshop.files import (
    MAX_DOCUMENT_BYTES,
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    replace_under,
    sha256_under,
)
from agency.workshop.sandbox import Sandbox


class ProjectState(TypedDict):
    """The graph's state, kept in the checkpoint. Any `outcome` text ends the run; `route` is a node's choice
    of the next one."""

    project: str
    root: str
    round: int
    client_note: str
    outcome: str
    explore: bool
    exploration: int
    chosen: str
    route: str


class Runner(Protocol):
    """What the graph asks of the agents: one instance on a ticket. `AgentRunner` is one."""

    def run(
        self, ticket_id: str, attempt: int = 1, rework_note: str = "", mode: str = "", exploration: int = 0
    ) -> Outcome: ...


@dataclass(frozen=True)
class Crew:
    """What the nodes work with: who runs the agents, the registry and the settings."""

    runner: Runner
    ledger: Ledger
    settings: Settings

    def work_dir(self, project: str) -> Path:
        return self.settings.work_dir(parse_project_name(project))


class Node(Protocol):
    """A graph node. LangGraph passes the state by the name `state`, so the protocol names it."""

    def __call__(self, state: Any) -> dict: ...


type Router = Callable[[ProjectState], list[Send] | str]


def attempt(ledger: Ledger, ticket: str) -> int:
    return 1 + sum(1 for event in ledger.history(ticket) if event.action in ("rework", "resume"))


def rework_note(ledger: Ledger, ticket: str) -> str:
    return next((e.note for e in reversed(ledger.history(ticket)) if e.action == "rework"), "")


type Graph = CompiledStateGraph[ProjectState, None, ProjectState, ProjectState]


def copy_capped(work: Path, source: str, target: str, limit: int) -> None:
    """A copy inside the work folder: a sandbox may leave a link at either end, and none is followed.

    The source is read whole, so a file over `limit` is refused."""
    replace_under(work, target, read_under(work, source, limit))


# Exploration


def plan(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        turn = state["exploration"] + 1
        note = f"Esploratori disponibili: {crew.settings.explorers}. {state['client_note']}"
        outcome = crew.runner.run(state["root"], turn, note.strip(), mode="plan")
        if outcome.state is OutcomeState.BLOCKED:
            return {"exploration": turn, "outcome": f"bloccato: {outcome.note}"}
        return {"exploration": turn, "client_note": ""}

    return node


def send_explorers(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | str:
        if state["outcome"]:
            return END
        rows = crew.ledger.concepts(state["project"], state["exploration"])
        sends = [
            Send("explore", {"ticket": row.idea_ticket})
            for row in rows
            if crew.ledger.status(row.idea_ticket)[0] in RUNNABLE
        ]
        return sends or "make_board"

    return route


def explore(crew: Crew) -> Node:
    def node(state: Any) -> dict:
        crew.runner.run(state["ticket"], attempt(crew.ledger, state["ticket"]))
        return {}

    return node


# Selection


def make_board(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        done = (Status.DELIVERED, Status.ACCEPTED)
        rows = [
            row
            for row in crew.ledger.concepts(project, turn)
            if crew.ledger.status(row.idea_ticket)[0] in done
        ]
        if not rows:
            return {"outcome": "bloccato: nessuna esplorazione consegnata"}
        anon = board.assign_letters(project, turn, [row.letter for row in rows])
        work = crew.work_dir(project)
        items = []
        for row in rows:
            file = f"explorations/r{turn}/{row.letter}/schizzo-{row.letter}.png"
            crew.ledger.update_concept(row.idea_ticket, anon=anon[row.letter], sketch_file=file)
            items.append((anon[row.letter], work / file))
            if crew.ledger.status(row.idea_ticket)[0] is Status.DELIVERED:
                crew.ledger.apply(row.idea_ticket, Action.ACCEPT, "design-director", "passa alla tavola")
        folder = f"board/r{turn}"
        board.build(items, work / folder / "tavola.png")
        copy_capped(work, "brief.md", f"{folder}/brief.md", MAX_TEXT_FILE_BYTES)
        return {}

    return node


def after_board(state: ProjectState) -> str:
    return END if state["outcome"] else "board_review"


def board_review(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        children = crew.ledger.children(state["root"])
        title = f"Tavola delle idee r{turn}"
        existing = [ticket for ticket in children if crew.ledger.spec(ticket).title == title]
        if existing:
            ticket = existing[0]
        else:
            spec = TicketSpec(
                title=title,
                request="Giudica le idee sulla tavola, rispetto a brief.md.",
                type=TicketType.REVIEW,
                sender="design-director",
                assignee="critic",
                outputs=["tavola.png", "reviews/selezione.md", "reviews/valutazione.json"],
                checks={"tavola.png": ["board_review"]},
                exempt={"reviews/valutazione.json": "il primo sguardo lo registra rate_board"},
                parent=state["root"],
                workspace=f"board/r{turn}",
                prompt="critic-board",
            )
            ticket = crew.ledger.open(spec, project)
        if crew.ledger.status(ticket)[0] in RUNNABLE:
            crew.runner.run(ticket, exploration=turn)
        return {}

    return node


def select(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        """The choice among the sketches is the studio's: the client never sees them."""
        project, turn = state["project"], state["exploration"]
        work = crew.work_dir(project)
        lines = ["# Schede delle idee", ""]
        for row in crew.ledger.concepts(project, turn):
            if row.anon:
                card = ConceptCard.model_validate_json(row.card_json)
                lines += [f"## {row.anon}", card.concept, f"Fatto: {card.client_fact}", ""]
                lines += [f"Non ovvia: {card.why_not_obvious}", f"Sostituzione: {card.substitution}", ""]
        folder = f"board/r{turn}"
        replace_under(work, f"{folder}/schede.md", "\n".join(lines).encode("utf-8"))
        ensure_dir_under(work, f"{folder}/fogli")
        for row in crew.ledger.concepts(project, turn):
            if not row.anon:
                continue
            try:  # a missing sheet is skipped; a link is refused, not followed
                sheet = read_under(
                    work, f"explorations/r{turn}/{row.letter}/foglio-{row.letter}.png", MAX_IMAGE_FILE_BYTES
                )
            except FileNotFoundError:
                continue
            replace_under(work, f"{folder}/fogli/{row.anon}.png", sheet)
        note = (
            f"Tavola: {folder}/tavola.png. Primo sguardo: {folder}/reviews/valutazione.json. "
            f"Critica: {folder}/reviews/selezione.md. Schede: {folder}/schede.md. "
            f"Tutte le miniature di ogni idea: {folder}/fogli/<lettera>.png."
        )
        outcome = crew.runner.run(state["root"], turn, note, mode="select")
        for ticket in crew.ledger.children(state["root"]):
            spec = crew.ledger.spec(ticket)
            if spec.prompt == "critic-board" and crew.ledger.status(ticket)[0] is Status.DELIVERED:
                crew.ledger.apply(ticket, Action.ACCEPT, spec.sender, "referto letto")
        if outcome.state is OutcomeState.SELECTED:
            return {"route": "prepare_proposals", "client_note": ""}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = SelectConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le idee precedenti non reggono: {reasons}"}
        return {"route": END, "outcome": f"bloccato: {outcome.note[:300]}"}

    return node


# Proposals: the chosen ideas become presentable work, in their context


def _proposal_tickets(crew: Crew, state: ProjectState) -> list[str]:
    suffix = f"r{state['exploration']}"
    return [
        ticket
        for ticket in crew.ledger.children(state["root"])
        if crew.ledger.spec(ticket).type is TicketType.PROPOSAL
        and crew.ledger.spec(ticket).title.endswith(suffix)
    ]


def prepare_proposals(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn, root = state["project"], state["exploration"], state["root"]
        work = crew.work_dir(project)
        existing = {crew.ledger.spec(ticket).title for ticket in _proposal_tickets(crew, state)}
        applications = json.loads(
            read_under(work, f"explorations/r{turn}/applicazioni.json", MAX_TEXT_FILE_BYTES).decode("utf-8")
        )
        chosen = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.SELECTED]
        for row in sorted(chosen, key=lambda item: item.anon):
            title = f"Proposta {row.anon} r{turn}"
            if title in existing:  # a replay: the ticket was opened, the status may not have been set
                crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
                continue
            letter = row.anon.lower()
            workspace = f"proposals/r{turn}/{letter}"
            ensure_dir_under(work, workspace)
            source = f"explorations/r{turn}/{row.letter}"
            copy_capped(work, "brief.md", f"{workspace}/brief.md", MAX_TEXT_FILE_BYTES)
            copy_capped(work, f"{source}/scheda.json", f"{workspace}/scheda.json", MAX_TEXT_FILE_BYTES)
            copy_capped(work, row.sketch_file, f"{workspace}/schizzo.png", MAX_IMAGE_FILE_BYTES)
            names = "\n".join(f"- {item['name']}: {item['size']}" for item in applications)
            spec = TicketSpec(
                title=title,
                request=f"Sviluppa questa idea in una proposta.\n\n{row.card_json}\n\nAPPLICAZIONI\n{names}",
                type=TicketType.PROPOSAL,
                sender="design-director",
                assignee="identity-designer",
                outputs=[
                    f"proposta-{letter}.vectorcraft",
                    f"proposta-{letter}.svg",
                    f"proposta-{letter}.png",
                    f"applicazioni-{letter}/*.png",
                ],
                checks={
                    "*.vectorcraft": ["master_open"],
                    "*.svg": ["svg_audit"],
                    "*.png": ["visual_review"],
                },
                media=[Medium.VECTOR],
                inputs=["scheda.json", "schizzo.png"],
                parent=root,
                workspace=workspace,
                prompt="proposer",
                effort=crew.settings.proposal_effort,
            )
            hashes = {path: sha256_under(work, f"{workspace}/{path}") for path in spec.inputs}
            crew.ledger.open(spec, project, hashes)
            crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.IN_DEVELOPMENT)
        return {}

    return node


def send_proposals(crew: Crew) -> Router:
    def route(state: ProjectState) -> list[Send] | str:
        tickets = [t for t in _proposal_tickets(crew, state) if crew.ledger.status(t)[0] in RUNNABLE]
        return [Send("proposal", {"ticket": ticket}) for ticket in tickets] or "present"

    return route


def proposal(crew: Crew) -> Node:
    def node(state: Any) -> dict:
        crew.runner.run(state["ticket"], attempt(crew.ledger, state["ticket"]))
        return {}

    return node


def present(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn, root = state["project"], state["exploration"], state["root"]
        concepts = {
            f"Proposta {row.anon} r{turn}": row for row in crew.ledger.concepts(project, turn) if row.anon
        }
        lines = ["# Proposte sviluppate", ""]
        for ticket in _proposal_tickets(crew, state):
            status, _ = crew.ledger.status(ticket)
            title = crew.ledger.spec(ticket).title
            if status is Status.DELIVERED:
                crew.ledger.apply(ticket, Action.ACCEPT, "design-director", "pronta per la presentazione")
            if crew.ledger.status(ticket)[0] is not Status.ACCEPTED:
                continue
            row = concepts[title]
            crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.PROPOSAL)
            mark, applications = presentation.proposal_files(
                crew.work_dir(project), turn, row.anon, crew.ledger.delivered(ticket)
            )
            view = f"proposals/r{turn}/insieme-{row.anon.lower()}.png"
            presentation.sheet(mark, applications, crew.work_dir(project) / view)
            card = ConceptCard.model_validate_json(row.card_json)
            lines += [
                f"## {row.anon}",
                f"Da guardare: {view}",
                card.concept,
                f"Fatto: {card.client_fact}",
                "",
            ]
        ready = [row for row in crew.ledger.concepts(project, turn) if row.status == ConceptStatus.PROPOSAL]
        if not ready:
            return {"route": END, "outcome": "bloccato: nessuna proposta è stata sviluppata"}
        outcome = crew.runner.run(root, turn, "\n".join(lines), mode="present")
        if outcome.state is OutcomeState.PRESENTED:  # the PDF exists, and the director viewed every page
            return {"route": "concept_gate", "client_note": outcome.note}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = PresentConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le proposte non reggono: {reasons}"}
        return {"route": END, "outcome": f"bloccato: {outcome.note[:300]}"}

    return node


def concept_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        selection = PresentConcepts.model_validate_json(state["client_note"])
        if selection.recommended is None:  # draft_presentation refuses a draft without a recommendation
            raise ValueError("a presentation without a recommendation never reaches the gate")
        options = [item.letter for item in selection.proposals]
        file = presentation.pdf_of(turn)
        gate = ConceptGate(
            ticket=state["root"],
            files=[file],
            options=options,
            recommended=selection.recommended,
            reasons=selection.reasons,
        )
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        digest = {file: sha256_under(crew.work_dir(project), file)}
        choice = decision.choice
        approved = decision.approved and choice in options
        recorded = {gate.files_json for gate in crew.ledger.gates(project) if gate.gate == "concept"}
        if json.dumps(digest) not in recorded:
            crew.ledger.add_gate(
                GateRow(
                    at=now(),
                    project=project,
                    gate="concept",
                    approved=approved,
                    choice=choice,
                    text=decision.text,
                    files_json=json.dumps(digest),
                )
            )
        if approved:
            return {"route": "start_production", "chosen": choice, "client_note": decision.text}
        return {"route": "plan", "client_note": f"Il cliente chiede: {decision.text}"}

    return node


def follow_route(state: ProjectState) -> str:
    return state["route"]


# Production


def start_production(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        """The finisher starts from the approved proposal: its master is already the one the client chose."""
        project, turn, root = state["project"], state["exploration"], state["root"]
        spec = crew.ledger.spec(root)
        row = next(item for item in crew.ledger.concepts(project, turn) if item.anon == state["chosen"])
        crew.ledger.update_concept(row.idea_ticket, status=ConceptStatus.CHOSEN)
        title = f"Rifinitura {row.anon} r{turn}"  # per round: a rejected concept makes way for the new one
        if any(crew.ledger.spec(ticket).title == title for ticket in crew.ledger.children(root)):
            return {"client_note": ""}
        letter = row.anon.lower()
        folder = f"proposals/r{turn}/{letter}"
        work = crew.work_dir(project)
        target = next(path for path in spec.outputs if path.endswith(".vectorcraft"))
        if PurePosixPath(target).parent.parts:
            ensure_dir_under(work, str(PurePosixPath(target).parent))
        copy_capped(work, f"{folder}/proposta-{letter}.vectorcraft", target, MAX_DOCUMENT_BYTES)
        production = TicketSpec(
            title=title,
            request=f"{spec.request}\n\nCONCETTO SCELTO DAL CLIENTE\n{row.card_json}\n\n"
            f"Il cliente ha detto: {state['client_note']}",
            type=TicketType.PRODUCTION,
            sender="design-director",
            assignee="identity-designer",
            outputs=spec.outputs,
            checks={
                pattern: [name for name in names if name != "critique"]
                for pattern, names in spec.checks.items()
            },
            exempt=spec.exempt,
            media=[Medium.VECTOR],
            inputs=[f"{folder}/scheda.json", f"{folder}/proposta-{letter}.png"],
            parent=root,
            prompt="finisher",
        )
        hashes = {path: sha256_under(work, path) for path in production.inputs}
        crew.ledger.open(production, project, hashes)
        return {"client_note": ""}

    return node


def lead(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        root, turn = state["root"], state["round"] + 1
        status, _ = crew.ledger.status(root)
        if status in RUNNABLE:
            # Each of the director's turns is a new instance: nobody sits waiting.
            outcome = crew.runner.run(root, turn, state["client_note"])
            if outcome.state is OutcomeState.BLOCKED:
                return {"round": turn, "outcome": f"bloccato: {outcome.note}"}
            if outcome.state is OutcomeState.CONCEPT_REJECTED:
                return {
                    "round": turn,
                    "route": "rejected",
                    "client_note": f"Concetto bocciato: {outcome.note}",
                }
        return {"round": turn, "client_note": "", "route": ""}

    return node


def team(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        for ticket in crew.ledger.children(state["root"]):
            status, _ = crew.ledger.status(ticket)
            if status in RUNNABLE:
                crew.runner.run(ticket, attempt(crew.ledger, ticket), rework_note(crew.ledger, ticket))
        return {}

    return node


def client_gate(crew: Crew) -> Node:
    def node(state: ProjectState) -> dict:
        root = state["root"]
        gate = FinalGate(ticket=root, files=sorted(crew.ledger.delivered(root)))
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        if crew.ledger.status(root)[0] is Status.ACCEPTED:
            return {"outcome": "approvato"}
        if not decision.approved:
            crew.ledger.apply(root, Action.REWORK, "router", decision.text or "il cliente chiede modifiche")
            return {"client_note": decision.text, "outcome": ""}
        project = state["project"]
        sandbox = Sandbox(crew.work_dir(project), crew.settings.toolchain_dir)
        problems = delivery.acceptance_problems(crew.ledger, project, sandbox, root)
        if problems:
            text = "Accettazione rifiutata dal sistema:\n" + "\n".join(problems[:12])
            crew.ledger.apply(root, Action.REWORK, "router", text)
            return {"client_note": text, "outcome": ""}
        crew.ledger.apply(root, Action.ACCEPT, "router", decision.text)
        return {"outcome": "approvato"}

    return node


def begin(state: ProjectState) -> str:
    return "plan" if state["explore"] else "lead"


def after_lead(crew: Crew) -> Router:
    def route(state: ProjectState) -> str:
        if state["outcome"]:
            return END
        if state["route"] == "rejected":
            return "plan"
        status, _ = crew.ledger.status(state["root"])
        if status is Status.DELIVERED:
            return "client_gate"
        if status in (Status.BLOCKED, Status.CANCELLED, Status.ACCEPTED):
            return END
        return "team"

    return route


def after_gate(state: ProjectState) -> str:
    return END if state["outcome"] else "lead"


def build(
    runner: AgentRunner, ledger: Ledger, settings: Settings, checkpointer: BaseCheckpointSaver
) -> Graph:
    """The compiled studio graph. `checkpointer` keeps its state, so a run stopped at a gate resumes."""
    crew = Crew(runner, ledger, settings)
    graph = StateGraph(ProjectState)
    nodes: tuple[tuple[str, Any], ...] = (
        ("plan", plan(crew)),
        ("explore", explore(crew)),
        ("make_board", make_board(crew)),
        ("board_review", board_review(crew)),
        ("select", select(crew)),
        ("prepare_proposals", prepare_proposals(crew)),
        ("proposal", proposal(crew)),
        ("present", present(crew)),
        ("concept_gate", concept_gate(crew)),
        ("start_production", start_production(crew)),
        ("lead", lead(crew)),
        ("team", team(crew)),
        ("client_gate", client_gate(crew)),
    )
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_conditional_edges(START, begin, ["plan", "lead"])
    graph.add_conditional_edges("plan", send_explorers(crew), ["explore", "make_board", END])
    graph.add_edge("explore", "make_board")
    graph.add_conditional_edges("make_board", after_board, ["board_review", END])
    graph.add_edge("board_review", "select")
    graph.add_conditional_edges("select", follow_route, ["prepare_proposals", "plan", END])
    graph.add_conditional_edges("prepare_proposals", send_proposals(crew), ["proposal", "present"])
    graph.add_edge("proposal", "present")
    graph.add_conditional_edges("present", follow_route, ["concept_gate", "plan", END])
    graph.add_conditional_edges("concept_gate", follow_route, ["start_production", "plan", END])
    graph.add_edge("start_production", "lead")
    graph.add_conditional_edges("lead", after_lead(crew), ["team", "client_gate", "plan", END])
    graph.add_edge("team", "lead")
    graph.add_conditional_edges("client_gate", after_gate, ["lead", END])
    return graph.compile(checkpointer=checkpointer)
