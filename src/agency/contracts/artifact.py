"""Gli artefatti per hash: una versione di un file che non cambia più, ritrovabile dal suo sha256.

La porta `ArtifactStore` sta qui, con i contratti: chi conserva dipende dalla porta, non dal disco. Oggi
c'è un deposito su file (`agency.artifacts.FileStore`); con il SaaS ce ne sarà uno per cliente.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol

from pydantic import BaseModel, ConfigDict, Field

SHA256 = re.compile(r"[0-9a-f]{64}")


class Origin(StrEnum):
    """Perché una versione si conserva: è stata consegnata, mostrata al cliente o giudicata."""

    DELIVERY = "consegna"
    PRESENTATION = "presentazione"
    JUDGMENT = "giudizio"


class Blob(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(pattern=SHA256.pattern)
    size: int = Field(ge=0, description="Byte")


class ArtifactMissing(KeyError):
    """Nessuna versione conservata con questo hash."""


class ArtifactStore(Protocol):
    def put(self, source: Path) -> Blob:
        """Conserva il contenuto attuale del file. Lo stesso contenuto si conserva una volta sola."""
        ...

    def open(self, sha256: str) -> BinaryIO:
        """Il contenuto conservato. `ArtifactMissing` se non c'è, `ValueError` se l'hash non è un sha256."""
        ...

    def exists(self, sha256: str) -> bool: ...

    def intact(self, sha256: str) -> bool:
        """Vero solo se il contenuto c'è e ha ancora il suo hash."""
        ...
