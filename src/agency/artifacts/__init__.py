"""Piattaforma: le versioni conservate dei file, ritrovabili dal loro sha256 (ADR-0028)."""

from agency.artifacts import keeping
from agency.artifacts.files import FileStore

__all__ = ["FileStore", "keeping"]
