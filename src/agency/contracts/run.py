"""A run's fingerprint: what decides how the run behaves, besides the brief."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class RunCommand(StrEnum):
    """The command that made the graph work: each one is a run with its own fingerprint."""

    RUN = "run"
    RESUME = "resume"
    DECIDE = "decide"


class Fingerprint(BaseModel):
    """Recorded with each run (`Ledger.record_run`); `changes` lists what differs between two of them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = Field(
        description="The client's choice; empty means each role's model in registry/roles.json"
    )
    effort: str = Field(description="The client's choice; empty means the ticket's or the role's effort")
    explorer_effort: str
    proposal_effort: str
    explorers: int
    max_parallel: int
    prompts: dict[str, str] = Field(description="Path → sha256 of each file in prompts/")
    registry: dict[str, str] = Field(description="Path → sha256 of each file in registry/")
    code: dict[str, str] = Field(description="Path → sha256 of each file in src/agency/")
    lock: str = Field(description="sha256 of uv.lock")
    python: str
    tools: dict[str, str] = Field(description="CLI → first line of --version")

    def digest(self) -> str:
        """Equal for two equal fingerprints, whatever order the files were read in."""
        canonical = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


def read_fingerprint(text: str) -> Fingerprint | None:
    """The fingerprint stored in `text`, or None when it has a shape this version does not read."""
    try:
        return Fingerprint.model_validate_json(text)
    except ValidationError:
        return None


class Change(BaseModel):
    """One difference between two fingerprints. `None` means the item is missing on that side."""

    model_config = ConfigDict(frozen=True)

    part: str
    item: str = ""
    before: str | None
    after: str | None


def changes(before: Fingerprint, after: Fingerprint) -> list[Change]:
    """The differences in the fingerprint's field order, and by name within each mapping."""
    found: list[Change] = []
    for part in Fingerprint.model_fields:
        old, new = getattr(before, part), getattr(after, part)
        if isinstance(old, dict):
            for item in sorted(old.keys() | new.keys()):
                if old.get(item) != new.get(item):
                    found.append(Change(part=part, item=item, before=old.get(item), after=new.get(item)))
        elif old != new:
            found.append(Change(part=part, before=str(old), after=str(new)))
    return found
