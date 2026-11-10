"""The store on disk: `<root>/<ab>/<sha256>`, one read-only file per content.

A file first lands in `.incoming/`, hashed while it is copied, and takes its name only once it is complete
and on disk: a reader never sees half a content. The first two hex digits split the files into smaller
folders.
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
    """Makes a rename in `folder` durable: the new name survives a power loss right after it."""
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class FileStore:
    """Content-addressed: each content is one read-only file named by its sha256, written atomically."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def location(self, sha256: str) -> Path:
        """Where a content lives; anything but a sha256 is refused before it reaches a path."""
        if not SHA256.fullmatch(sha256):
            raise ValueError(f"not a sha256: {sha256!r}")
        return self.root / sha256[:2] / sha256

    def put(self, source: BinaryIO) -> Blob:
        """Stores what `source` holds and returns its sha256 and size."""
        incoming = self.root / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=incoming)
        temporary = Path(name)
        try:
            digest, size = hashlib.sha256(), 0
            with os.fdopen(descriptor, "wb") as copy:
                while chunk := source.read(CHUNK):
                    digest.update(chunk)
                    copy.write(chunk)
                    size += len(chunk)
                copy.flush()
                os.fsync(copy.fileno())
            blob = Blob(sha256=digest.hexdigest(), size=size)
            # New, or damaged in the store: either way the fresh copy takes its place.
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
        """The stored content, or ArtifactMissing when the store has lost it."""
        target = self.location(sha256)
        if not target.is_file():
            raise ArtifactMissing(sha256)
        return target.open("rb")

    def exists(self, sha256: str) -> bool:
        return self.location(sha256).is_file()

    def intact(self, sha256: str) -> bool:
        """Whether the stored file exists and still hashes to its name: a full read."""
        target = self.location(sha256)
        return target.is_file() and _digest(target) == sha256
