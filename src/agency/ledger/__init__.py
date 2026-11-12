"""The work registry: the studio's tables in SQLite, with an append-only, hash-chained history of events.

The tables hold the current state; the chain does not rebuild it, it proves it. Each version-2 event binds
the state it leaves behind: a ticket's status, verdict, delivered hashes and contract, or the idea, gate,
proof, paid call or project it writes. `agency verify` therefore finds a change made outside the ledger
(ADR-0047, ADR-0049, ADR-0050).
"""

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
