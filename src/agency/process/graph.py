"""The studio's process: first the idea is found, then it is built.

inside the studio: explorers who think by drawing, in parallel → anonymous board → the critic's first
look → choice of ideas → proposals in parallel
in front of the client: presentation → `concept` gate → finishing → revisions → `final` gate

The graph knows where the work is; the registry knows what happened. On resume a node runs again from the
start: finished work is not repeated, because each instance has a stable name and its own transcript.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agency.agents.loop import AgentRunner
from agency.config import Settings
from agency.contracts.ledger import LedgerPort
from agency.contracts.project import parse_project_name
from agency.contracts.registry import StudioRules
from agency.contracts.ticket import Status
from agency.studio.delivery.nodes import client_gate
from agency.studio.exploration.nodes import explore, plan, send_explorers
from agency.studio.graph import Router
from agency.studio.presentation.nodes import concept_gate, present
from agency.studio.proposal.nodes import prepare_proposals, proposal, send_proposals
from agency.studio.refinement.nodes import lead, start_production, team
from agency.studio.selection.nodes import board_review, make_board, select
from agency.studio.shared import END_ROUTE, Crew, ProjectState, Route
from agency.workshop.sandbox import Sandbox

type Graph = CompiledStateGraph[ProjectState, None, ProjectState, ProjectState]


def after_board(state: ProjectState) -> Route:
    return END_ROUTE if state["outcome"] else "board_review"


def follow_route(state: ProjectState) -> Route:
    return state["route"]


def begin(state: ProjectState) -> Route:
    return "plan" if state["explore"] else "lead"


def after_lead(crew: Crew) -> Router:
    def route(state: ProjectState) -> Route:
        if state["outcome"]:
            return END_ROUTE
        if state["route"] == "rejected":
            return "plan"
        status, _ = crew.ledger.status(state["root"])
        if status is Status.DELIVERED:
            return "client_gate"
        if status in (Status.BLOCKED, Status.CANCELLED, Status.ACCEPTED):
            return END_ROUTE
        return "team"

    return route


def after_gate(state: ProjectState) -> Route:
    return END_ROUTE if state["outcome"] else "lead"


def build(
    runner: AgentRunner,
    ledger: LedgerPort,
    settings: Settings,
    checkpointer: BaseCheckpointSaver,
    rules: StudioRules,
) -> Graph:
    """The compiled studio graph. `checkpointer` keeps its state, so a run stopped at a gate resumes."""

    def sandbox_for(project: str) -> Sandbox:
        return Sandbox(settings.work_dir(parse_project_name(project)), settings.toolchain_dir)

    crew = Crew(runner, ledger, settings, rules, sandbox_for)
    graph = StateGraph(ProjectState)
    graph.add_node("plan", plan(crew))
    graph.add_node("explore", explore(crew))
    graph.add_node("make_board", make_board(crew))
    graph.add_node("board_review", board_review(crew))
    graph.add_node("select", select(crew))
    graph.add_node("prepare_proposals", prepare_proposals(crew))
    graph.add_node("proposal", proposal(crew))
    graph.add_node("present", present(crew))
    graph.add_node("concept_gate", concept_gate(crew))
    graph.add_node("start_production", start_production(crew))
    graph.add_node("lead", lead(crew))
    graph.add_node("team", team(crew))
    graph.add_node("client_gate", client_gate(crew))
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
