"""A call's phase is the prompt the instance works with: a role can have more than one.

The engine uses these rules to work; `insights` uses them to derive the phase of the calls recorded before
`usage` stored it. There is one rule, so the two cannot diverge.
"""

from __future__ import annotations

import re
from typing import Literal

# The director's phases on the same ticket, told apart by the suffix of the instance name.
type DirectorMode = Literal["plan", "select", "present"]
MODES: dict[DirectorMode, str] = {
    "plan": "director-plan",
    "select": "director-select",
    "present": "director-present",
}
INSTANCE = re.compile(r"T-\d+-a\d+(?:-(?P<mode>[a-z]+))?")


def instance(ticket_id: str, attempt: int, mode: DirectorMode | None = None) -> str:
    """The instance name, `<ticket>-a<attempt>` plus `-<mode>` for a director phase: `INSTANCE` parses it."""
    return f"{ticket_id}-a{attempt}" + (f"-{mode}" if mode else "")


def mode_of(name: str) -> DirectorMode | None:
    """The director phase written in the instance name, or None."""
    match = INSTANCE.fullmatch(name)
    written = match["mode"] if match else None
    return next((mode for mode in MODES if mode == written), None)


def of(role: str, prompt: str = "", mode: DirectorMode | None = None) -> str:
    """The phase: the director's if there is one, else the ticket's prompt, else the role."""
    return (MODES[mode] if mode is not None else "") or prompt or role
