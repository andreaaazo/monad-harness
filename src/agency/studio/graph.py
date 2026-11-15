"""The types the slices' nodes show LangGraph: a node and a router. Only the graph adapters import this
module, each slice's `nodes.py` and the process, so the rest of the studio stays free of LangGraph
(ADR-0058)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langgraph.types import Send

from agency.studio.shared import ProjectState, ProjectUpdate, Route, TicketTask


class Node(Protocol):
    """A graph node. LangGraph passes the state by the name `state`, so the protocol names it."""

    def __call__(self, state: ProjectState) -> ProjectUpdate: ...


class TaskNode(Protocol):
    """A node reached by `Send`: it receives the ticket it works on, not the state."""

    def __call__(self, state: TicketTask) -> ProjectUpdate: ...


type Router = Callable[[ProjectState], list[Send] | Route]
