"""La fase di una chiamata è il prompt con cui l'istanza lavora: un ruolo può averne più d'una.

Il motore usa queste regole per lavorare; `insights` le usa per ricavare la fase delle chiamate registrate
prima che `usage` la salvasse. Una sola regola, così le due cose non possono divergere.
"""

from __future__ import annotations

import re

# Le fasi del direttore sullo stesso ticket: si riconoscono dal suffisso del nome dell'istanza.
MODES: dict[str, str] = {"plan": "director-plan", "select": "director-select", "present": "director-present"}
INSTANCE = re.compile(r"T-\d+-a\d+(?:-(?P<mode>[a-z]+))?")


def instance(ticket_id: str, attempt: int, mode: str = "") -> str:
    return f"{ticket_id}-a{attempt}" + (f"-{mode}" if mode else "")


def mode_of(name: str) -> str:
    """La fase del direttore scritta nel nome dell'istanza, o vuoto."""
    match = INSTANCE.fullmatch(name)
    mode = match["mode"] if match else None
    return mode if mode in MODES else ""


def of(role: str, prompt: str = "", mode: str = "") -> str:
    """La fase: quella del direttore se c'è, poi il prompt del ticket, poi il ruolo."""
    return MODES.get(mode) or prompt or role
