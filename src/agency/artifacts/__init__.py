"""Platform: the kept versions of files, found again by their sha256 (ADR-0028)."""

from agency.artifacts import keeping
from agency.artifacts.files import FileStore

__all__ = ["FileStore", "keeping"]
