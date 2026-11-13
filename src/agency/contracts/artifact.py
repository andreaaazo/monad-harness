"""Artifacts by hash: a version of a file that never changes again, found by its sha256.

The `ArtifactStore` port lives here, with the contracts, so whatever keeps versions depends on the port, not
on the disk. Today there is one file store (`agency.artifacts.FileStore`); the SaaS will have one per client.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import BinaryIO, Protocol

from pydantic import BaseModel, ConfigDict, Field

SHA256 = re.compile(r"[0-9a-f]{64}")


class Origin(StrEnum):
    """Why a version is kept: it was delivered, shown to the client, or judged."""

    DELIVERY = "consegna"
    PRESENTATION = "presentazione"
    JUDGMENT = "giudizio"


class Blob(BaseModel):
    """What `ArtifactStore.put` returns: the kept content's sha256 and its size."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(pattern=SHA256.pattern)
    size: int = Field(ge=0, description="In bytes")


class ArtifactMissing(KeyError):
    """No version is kept under this hash."""


class ArtifactStore(Protocol):
    """Keeps file versions by content: each one is stored once, under its sha256, and never changes."""

    def put(self, source: BinaryIO) -> Blob:
        """Keeps the open file's current content. The same content is kept only once."""
        ...

    def open(self, sha256: str) -> BinaryIO:
        """The kept content. `ArtifactMissing` if there is none, `ValueError` if the hash is not a sha256."""
        ...

    def exists(self, sha256: str) -> bool: ...

    def intact(self, sha256: str) -> bool:
        """True only if the content is there and still has its hash."""
        ...
