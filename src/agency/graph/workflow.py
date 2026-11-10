"""The studio's process: first the idea is found, then it is built.

inside the studio: explorers who think by drawing, in parallel → anonymous board → the critic's first
look → choice of ideas → proposals in parallel
in front of the client: presentation → `concept` gate → finishing → revisions → `final` gate

The graph knows where the work is; the registry knows what happened. On resume a node runs again from the
start: finished work is not repeated, because each instance has a stable name and its own transcript.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send, interrupt

from agency.agents.loop import AgentRunner
from agency.config import Settings
from agency.contracts.concept import ConceptCard
from agency.contracts.gate import ConceptGate, Decision, FinalGate
from agency.contracts.outcome import OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.ledger.models import GateRow
from agency.ledger.store import now
from agency.qa import delivery
from agency.tools import board, presentation
from agency.tools.files import (
    MAX_DOCUMENT_BYTES,
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    ensure_dir_under,
    read_under,
    replace_under,
    sha256_under,
)
from agency.tools.sandbox import Sandbox
from agency.tools.surface import PresentConcepts, SelectConcepts

RUNNABLE = (Status.OPEN, Status.REWORK)
SKETCH_CHECKS = {"*.vectorcraft": ["master_open"], "*.png": ["visual_review"]}


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


def _attempt(ledger: Ledger, ticket: str) -> int:
    return 1 + sum(1 for event in ledger.history(ticket) if event.action in ("rework", "resume"))


def _rework_note(ledger: Ledger, ticket: str) -> str:
    return next((e.note for e in reversed(ledger.history(ticket)) if e.action == "rework"), "")


type Graph = CompiledStateGraph[ProjectState, None, ProjectState, ProjectState]


def _copy(work: Path, source: str, target: str, limit: int) -> None:
    """A copy inside the work folder: a sandbox may leave a link at either end, and none is followed.

    The source is read whole, so a file over `limit` is refused."""
    replace_under(work, target, read_under(work, source, limit))


def build(
    runner: AgentRunner, ledger: Ledger, settings: Settings, checkpointer: BaseCheckpointSaver
) -> Graph:
    """The compiled studio graph. `checkpointer` keeps its state, so a run stopped at a gate resumes."""

    def work_dir(project: str):
        return settings.project_dir(parse_project_name(project)) / "work"

    # Exploration

    def plan(state: ProjectState) -> dict:
        turn = state["exploration"] + 1
        note = f"Esploratori disponibili: {settings.explorers}. {state['client_note']}"
        outcome = runner.run(state["root"], turn, note.strip(), mode="plan")
        if outcome.state is OutcomeState.BLOCKED:
            return {"exploration": turn, "outcome": f"bloccato: {outcome.note}"}
        return {"exploration": turn, "client_note": ""}

    def send_explorers(state: ProjectState) -> list[Send] | str:
        if state["outcome"]:
            return END
        rows = ledger.concepts(state["project"], state["exploration"])
        sends = [
            Send("explore", {"ticket": row.idea_ticket})
            for row in rows
            if ledger.status(row.idea_ticket)[0] in RUNNABLE
        ]
        return sends or "make_board"

    def explore(state: Any) -> dict:
        runner.run(state["ticket"], _attempt(ledger, state["ticket"]))
        return {}

    # Selection

    def make_board(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        done = (Status.DELIVERED, Status.ACCEPTED)
        rows = [row for row in ledger.concepts(project, turn) if ledger.status(row.idea_ticket)[0] in done]
        if not rows:
            return {"outcome": "bloccato: nessuna esplorazione consegnata"}
        anon = board.assign_letters(project, turn, [row.letter for row in rows])
        work = work_dir(project)
        items = []
        for row in rows:
            file = f"explorations/r{turn}/{row.letter}/schizzo-{row.letter}.png"
            ledger.update_concept(row.idea_ticket, anon=anon[row.letter], sketch_file=file)
            items.append((anon[row.letter], work / file))
            if ledger.status(row.idea_ticket)[0] is Status.DELIVERED:
                ledger.apply(row.idea_ticket, Action.ACCEPT, "design-director", "passa alla tavola")
        folder = f"board/r{turn}"
        board.build(items, work / folder / "tavola.png")
        _copy(work, "brief.md", f"{folder}/brief.md", MAX_TEXT_FILE_BYTES)
        return {}

    def after_board(state: ProjectState) -> str:
        return END if state["outcome"] else "board_review"

    def board_review(state: ProjectState) -> dict:
        project, turn = state["project"], state["exploration"]
        children = ledger.children(state["root"])
        title = f"Tavola delle idee r{turn}"
        existing = [ticket for ticket in children if ledger.spec(ticket).title == title]
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
            ticket = ledger.open(spec, project)
        if ledger.status(ticket)[0] in RUNNABLE:
            runner.run(ticket, exploration=turn)
        return {}

    def select(state: ProjectState) -> dict:
        """The choice among the sketches is the studio's: the client never sees them."""
        project, turn = state["project"], state["exploration"]
        work = work_dir(project)
        lines = ["# Schede delle idee", ""]
        for row in ledger.concepts(project, turn):
            if row.anon:
                card = ConceptCard.model_validate_json(row.card_json)
                lines += [f"## {row.anon}", card.concept, f"Fatto: {card.client_fact}", ""]
                lines += [f"Non ovvia: {card.why_not_obvious}", f"Sostituzione: {card.substitution}", ""]
        folder = f"board/r{turn}"
        replace_under(work, f"{folder}/schede.md", "\n".join(lines).encode("utf-8"))
        ensure_dir_under(work, f"{folder}/fogli")
        for row in ledger.concepts(project, turn):
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
        outcome = runner.run(state["root"], turn, note, mode="select")
        for ticket in ledger.children(state["root"]):
            spec = ledger.spec(ticket)
            if spec.prompt == "critic-board" and ledger.status(ticket)[0] is Status.DELIVERED:
                ledger.apply(ticket, Action.ACCEPT, spec.sender, "referto letto")
        if outcome.state is OutcomeState.SELECTED:
            return {"route": "prepare_proposals", "client_note": ""}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = SelectConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le idee precedenti non reggono: {reasons}"}
        return {"route": END, "outcome": f"bloccato: {outcome.note[:300]}"}

    # Proposals: the chosen ideas become presentable work, in their context

    def _proposal_tickets(state: ProjectState) -> list[str]:
        suffix = f"r{state['exploration']}"
        return [
            ticket
            for ticket in ledger.children(state["root"])
            if ledger.spec(ticket).type is TicketType.PROPOSAL and ledger.spec(ticket).title.endswith(suffix)
        ]

    def prepare_proposals(state: ProjectState) -> dict:
        project, turn, root = state["project"], state["exploration"], state["root"]
        work = work_dir(project)
        existing = {ledger.spec(ticket).title for ticket in _proposal_tickets(state)}
        applications = json.loads(
            read_under(work, f"explorations/r{turn}/applicazioni.json", MAX_TEXT_FILE_BYTES).decode("utf-8")
        )
        chosen = [row for row in ledger.concepts(project, turn) if row.status == "selezionata"]
        for row in sorted(chosen, key=lambda item: item.anon):
            title = f"Proposta {row.anon} r{turn}"
            if title in existing:  # a replay: the ticket was opened, the status may not have been set
                ledger.update_concept(row.idea_ticket, status="in-sviluppo")
                continue
            letter = row.anon.lower()
            workspace = f"proposals/r{turn}/{letter}"
            ensure_dir_under(work, workspace)
            source = f"explorations/r{turn}/{row.letter}"
            _copy(work, "brief.md", f"{workspace}/brief.md", MAX_TEXT_FILE_BYTES)
            _copy(work, f"{source}/scheda.json", f"{workspace}/scheda.json", MAX_TEXT_FILE_BYTES)
            _copy(work, row.sketch_file, f"{workspace}/schizzo.png", MAX_IMAGE_FILE_BYTES)
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
                effort=settings.proposal_effort,
            )
            hashes = {path: sha256_under(work, f"{workspace}/{path}") for path in spec.inputs}
            ledger.open(spec, project, hashes)
            ledger.update_concept(row.idea_ticket, status="in-sviluppo")
        return {}

    def send_proposals(state: ProjectState) -> list[Send] | str:
        tickets = [t for t in _proposal_tickets(state) if ledger.status(t)[0] in RUNNABLE]
        return [Send("proposal", {"ticket": ticket}) for ticket in tickets] or "present"

    def proposal(state: Any) -> dict:
        runner.run(state["ticket"], _attempt(ledger, state["ticket"]))
        return {}

    def present(state: ProjectState) -> dict:
        project, turn, root = state["project"], state["exploration"], state["root"]
        concepts = {f"Proposta {row.anon} r{turn}": row for row in ledger.concepts(project, turn) if row.anon}
        lines = ["# Proposte sviluppate", ""]
        for ticket in _proposal_tickets(state):
            status, _ = ledger.status(ticket)
            title = ledger.spec(ticket).title
            if status is Status.DELIVERED:
                ledger.apply(ticket, Action.ACCEPT, "design-director", "pronta per la presentazione")
            if ledger.status(ticket)[0] is not Status.ACCEPTED:
                continue
            row = concepts[title]
            ledger.update_concept(row.idea_ticket, status="proposta")
            mark, applications = presentation.proposal_files(
                work_dir(project), turn, row.anon, ledger.delivered(ticket)
            )
            view = f"proposals/r{turn}/insieme-{row.anon.lower()}.png"
            presentation.sheet(mark, applications, work_dir(project) / view)
            card = ConceptCard.model_validate_json(row.card_json)
            lines += [
                f"## {row.anon}",
                f"Da guardare: {view}",
                card.concept,
                f"Fatto: {card.client_fact}",
                "",
            ]
        ready = [row for row in ledger.concepts(project, turn) if row.status == "proposta"]
        if not ready:
            return {"route": END, "outcome": "bloccato: nessuna proposta è stata sviluppata"}
        outcome = runner.run(root, turn, "\n".join(lines), mode="present")
        if outcome.state is OutcomeState.PRESENTED:  # the PDF exists, and the director viewed every page
            return {"route": "concept_gate", "client_note": outcome.note}
        if outcome.state is OutcomeState.NO_CONCEPT:
            reasons = PresentConcepts.model_validate_json(outcome.note).reasons
            return {"route": "plan", "client_note": f"Le proposte non reggono: {reasons}"}
        return {"route": END, "outcome": f"bloccato: {outcome.note[:300]}"}

    def concept_gate(state: ProjectState) -> dict:
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
        digest = {file: sha256_under(work_dir(project), file)}
        choice = decision.choice
        approved = decision.approved and choice in options
        recorded = {gate.files_json for gate in ledger.gates(project) if gate.gate == "concept"}
        if json.dumps(digest) not in recorded:
            ledger.add_gate(
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

    def follow_route(state: ProjectState) -> str:
        return state["route"]

    # Production

    def start_production(state: ProjectState) -> dict:
        """The finisher starts from the approved proposal: its master is already the one the client chose."""
        project, turn, root = state["project"], state["exploration"], state["root"]
        spec = ledger.spec(root)
        row = next(item for item in ledger.concepts(project, turn) if item.anon == state["chosen"])
        ledger.update_concept(row.idea_ticket, status="scelta")
        title = f"Rifinitura {row.anon} r{turn}"  # per round: a rejected concept makes way for the new one
        if any(ledger.spec(ticket).title == title for ticket in ledger.children(root)):
            return {"client_note": ""}
        letter = row.anon.lower()
        folder = f"proposals/r{turn}/{letter}"
        work = work_dir(project)
        target = next(path for path in spec.outputs if path.endswith(".vectorcraft"))
        if PurePosixPath(target).parent.parts:
            ensure_dir_under(work, str(PurePosixPath(target).parent))
        _copy(work, f"{folder}/proposta-{letter}.vectorcraft", target, MAX_DOCUMENT_BYTES)
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
        ledger.open(production, project, hashes)
        return {"client_note": ""}

    def lead(state: ProjectState) -> dict:
        root, turn = state["root"], state["round"] + 1
        status, _ = ledger.status(root)
        if status in RUNNABLE:
            # Each of the director's turns is a new instance: nobody sits waiting.
            outcome = runner.run(root, turn, state["client_note"])
            if outcome.state is OutcomeState.BLOCKED:
                return {"round": turn, "outcome": f"bloccato: {outcome.note}"}
            if outcome.state is OutcomeState.CONCEPT_REJECTED:
                return {
                    "round": turn,
                    "route": "rejected",
                    "client_note": f"Concetto bocciato: {outcome.note}",
                }
        return {"round": turn, "client_note": "", "route": ""}

    def team(state: ProjectState) -> dict:
        for ticket in ledger.children(state["root"]):
            status, _ = ledger.status(ticket)
            if status in RUNNABLE:
                runner.run(ticket, _attempt(ledger, ticket), _rework_note(ledger, ticket))
        return {}

    def client_gate(state: ProjectState) -> dict:
        root = state["root"]
        gate = FinalGate(ticket=root, files=sorted(ledger.delivered(root)))
        decision = Decision.model_validate(interrupt(gate.model_dump(mode="json")))
        if ledger.status(root)[0] is Status.ACCEPTED:
            return {"outcome": "approvato"}
        if not decision.approved:
            ledger.apply(root, Action.REWORK, "router", decision.text or "il cliente chiede modifiche")
            return {"client_note": decision.text, "outcome": ""}
        project = state["project"]
        sandbox = Sandbox(work_dir(project), settings.toolchain_dir)
        problems = delivery.acceptance_problems(ledger, project, sandbox, root)
        if problems:
            text = "Accettazione rifiutata dal sistema:\n" + "\n".join(problems[:12])
            ledger.apply(root, Action.REWORK, "router", text)
            return {"client_note": text, "outcome": ""}
        ledger.apply(root, Action.ACCEPT, "router", decision.text)
        return {"outcome": "approvato"}

    def begin(state: ProjectState) -> str:
        return "plan" if state["explore"] else "lead"

    def after_lead(state: ProjectState) -> str:
        if state["outcome"]:
            return END
        if state["route"] == "rejected":
            return "plan"
        status, _ = ledger.status(state["root"])
        if status is Status.DELIVERED:
            return "client_gate"
        if status in (Status.BLOCKED, Status.CANCELLED, Status.ACCEPTED):
            return END
        return "team"

    def after_gate(state: ProjectState) -> str:
        return END if state["outcome"] else "lead"

    graph = StateGraph(ProjectState)
    nodes: tuple[tuple[str, Any], ...] = (
        ("plan", plan),
        ("explore", explore),
        ("make_board", make_board),
        ("board_review", board_review),
        ("select", select),
        ("prepare_proposals", prepare_proposals),
        ("proposal", proposal),
        ("present", present),
        ("concept_gate", concept_gate),
        ("start_production", start_production),
        ("lead", lead),
        ("team", team),
        ("client_gate", client_gate),
    )
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_conditional_edges(START, begin, ["plan", "lead"])
    graph.add_conditional_edges("plan", send_explorers, ["explore", "make_board", END])
    graph.add_edge("explore", "make_board")
    graph.add_conditional_edges("make_board", after_board, ["board_review", END])
    graph.add_edge("board_review", "select")
    graph.add_conditional_edges("select", follow_route, ["prepare_proposals", "plan", END])
    graph.add_conditional_edges("prepare_proposals", send_proposals, ["proposal", "present"])
    graph.add_edge("proposal", "present")
    graph.add_conditional_edges("present", follow_route, ["concept_gate", "plan", END])
    graph.add_conditional_edges("concept_gate", follow_route, ["start_production", "plan", END])
    graph.add_edge("start_production", "lead")
    graph.add_conditional_edges("lead", after_lead, ["team", "client_gate", "plan", END])
    graph.add_edge("team", "lead")
    graph.add_conditional_edges("client_gate", after_gate, ["lead", END])
    return graph.compile(checkpointer=checkpointer)
