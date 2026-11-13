"""A call's phase is the prompt the instance works with: a role can have more than one.

The engine uses these rules to work; `insights` uses them to derive the phase of the calls recorded before
`usage` stored it. There is one rule, so the two cannot diverge.
"""

from __future__ import annotations

import re

# The director's phases on the same ticket, told apart by the suffix of the instance name.
MODES: dict[str, str] = {"plan": "director-plan", "select": "director-select", "present": "director-present"}
INSTANCE = re.compile(r"T-\d+-a\d+(?:-(?P<mode>[a-z]+))?")


def instance(ticket_id: str, attempt: int, mode: str = "") -> str:
    """The instance name, `<ticket>-a<attempt>` plus `-<mode>` for a director phase: `INSTANCE` parses it."""
    return f"{ticket_id}-a{attempt}" + (f"-{mode}" if mode else "")


def mode_of(name: str) -> str:
    """The director phase written in the instance name, or empty."""
    match = INSTANCE.fullmatch(name)
    mode = match["mode"] if match else None
    return mode if mode in MODES else ""


def of(role: str, prompt: str = "", mode: str = "") -> str:
    """The phase: the director's if there is one, else the ticket's prompt, else the role."""
    return MODES.get(mode) or prompt or role
