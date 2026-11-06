"""Registro del lavoro: stato derivato da eventi solo in aggiunta e concatenati per hash."""

from agency.ledger.schema import LedgerOutdated
from agency.ledger.store import (
    ForbiddenAction,
    IllegalTransition,
    Ledger,
    LedgerMissing,
    require_registry,
)

__all__ = [
    "ForbiddenAction",
    "IllegalTransition",
    "Ledger",
    "LedgerMissing",
    "LedgerOutdated",
    "require_registry",
]
