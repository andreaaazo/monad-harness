"""Il deposito su disco: `<radice>/<ab>/<sha256>`, un file in sola lettura per ogni contenuto.

Un file entra prima in `.incoming/`, con l'hash calcolato mentre lo si copia, e prende il suo nome solo
quando è completo e scritto su disco: chi legge non vede mai un contenuto a metà. Le due cifre iniziali
dividono i file in cartelle più piccole.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from agency.contracts.artifact import SHA256, ArtifactMissing, Blob

CHUNK = 1 << 20
READ_ONLY = 0o444


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _sync(folder: Path) -> None:
    """Il nome nuovo resta anche se la macchina si spegne subito dopo."""
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def location(self, sha256: str) -> Path:
        if not SHA256.fullmatch(sha256):
            raise ValueError(f"non è uno sha256: {sha256!r}")
        return self.root / sha256[:2] / sha256

    def put(self, source: Path) -> Blob:
        incoming = self.root / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=incoming)
        temporary = Path(name)
        try:
            digest, size = hashlib.sha256(), 0
            with os.fdopen(descriptor, "wb") as copy, source.open("rb") as original:
                while chunk := original.read(CHUNK):
                    digest.update(chunk)
                    copy.write(chunk)
                    size += len(chunk)
                copy.flush()
                os.fsync(copy.fileno())
            blob = Blob(sha256=digest.hexdigest(), size=size)
            # Nuovo, oppure danneggiato: in tutti e due i casi la copia appena fatta prende il suo posto.
            if not self.intact(blob.sha256):
                target = self.location(blob.sha256)
                target.parent.mkdir(exist_ok=True)
                temporary.chmod(READ_ONLY)
                os.replace(temporary, target)
                _sync(target.parent)
            return blob
        finally:
            temporary.unlink(missing_ok=True)

    def open(self, sha256: str) -> BinaryIO:
        target = self.location(sha256)
        if not target.is_file():
            raise ArtifactMissing(sha256)
        return target.open("rb")

    def exists(self, sha256: str) -> bool:
        return self.location(sha256).is_file()

    def intact(self, sha256: str) -> bool:
        target = self.location(sha256)
        return target.is_file() and _digest(target) == sha256
