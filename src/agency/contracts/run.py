"""L'impronta di un'esecuzione: ciò che ne decide il comportamento, oltre al brief e al modello."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class RunCommand(StrEnum):
    """Il comando che ha fatto lavorare il grafo: ognuno è un'esecuzione con la sua impronta."""

    RUN = "run"
    RESUME = "resume"
    DECIDE = "decide"


class Fingerprint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = Field(
        description="Scelta del cliente; vuoto vale il modello di ogni ruolo in registry/roles.json"
    )
    effort: str = Field(description="Scelta del cliente; vuoto vale l'effort del ticket o del ruolo")
    explorer_effort: str
    proposal_effort: str
    explorers: int
    max_parallel: int
    prompts: dict[str, str] = Field(description="Percorso → sha256 di ogni file in prompts/")
    registry: dict[str, str] = Field(description="Percorso → sha256 di ogni file in registry/")
    code: dict[str, str] = Field(description="Percorso → sha256 di ogni file in src/agency/")
    lock: str = Field(description="sha256 di uv.lock")
    python: str
    tools: dict[str, str] = Field(description="CLI → prima riga di --version")

    def digest(self) -> str:
        """Uguale per due impronte uguali, qualunque sia l'ordine in cui sono stati letti i file."""
        canonical = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


def read_fingerprint(text: str) -> Fingerprint | None:
    """The fingerprint stored in `text`, or None when it has a shape this version does not read."""
    try:
        return Fingerprint.model_validate_json(text)
    except ValidationError:
        return None


class Change(BaseModel):
    """Una differenza tra due impronte. `None` vuol dire che da quella parte l'elemento non c'è."""

    model_config = ConfigDict(frozen=True)

    part: str
    item: str = ""
    before: str | None
    after: str | None


def changes(before: Fingerprint, after: Fingerprint) -> list[Change]:
    """Le differenze nell'ordine dell'impronta, e dentro ogni elenco in ordine di nome."""
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
