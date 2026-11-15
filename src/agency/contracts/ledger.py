"""The ledger's contract with the engine: what it refuses and, from ADR-0058, the ports and entries the
engine reaches it through. `agency.ledger` implements it on SQLite."""

from __future__ import annotations


class IllegalTransition(Exception):
    """The action is not allowed from the ticket's current status."""


class ForbiddenAction(Exception):
    """The actor has no right to take the action."""
