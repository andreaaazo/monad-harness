"""A project's name: a DNS label, because it becomes the name of a folder (COR-013).

1 to 63 characters: lower-case letters, digits and hyphens, with no hyphen at the start or the end. A name
that follows the rule cannot leave the projects folder, and stays valid as a subdomain or a container name.
"""

from __future__ import annotations

import re
from typing import NewType

# Always with `fullmatch`: `match` would accept a text that only starts with a valid name, like "merlo\n".
PROJECT_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")

ProjectName = NewType("ProjectName", str)


def parse_project_name(text: str) -> ProjectName:
    """The one way to make a `ProjectName`: refuse, naming the value, any text the rule rejects."""
    if PROJECT_NAME.fullmatch(text) is None:
        raise ValueError(
            f"nome di progetto non valido: {text!r} (minuscole, cifre e trattini, da 1 a 63 caratteri,"
            " senza trattino all'inizio o alla fine)"
        )
    return ProjectName(text)
