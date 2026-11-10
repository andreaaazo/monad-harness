"""Percorsi e hash dentro il perimetro del lavoro."""

from __future__ import annotations

import hashlib
from pathlib import Path

from agency.contracts.files import (
    OutsidePerimeter,
    ensure_dir_under,
    inside,
    open_under,
    read_under,
    replace_under,
    sha256_under,
    write_new_under,
)

__all__ = [
    "OutsidePerimeter",
    "clip",
    "ensure_dir_under",
    "inside",
    "open_under",
    "read_under",
    "replace_under",
    "sha256",
    "sha256_under",
    "write_new_under",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clip(text: str, limit: int = 4000) -> str:
    """I risultati degli strumenti restano brevi: il dettaglio sta nei file."""
    if len(text) <= limit:
        return text
    head = limit * 3 // 4
    return f"{text[:head]}\n[… {len(text) - limit} caratteri omessi …]\n{text[-(limit - head) :]}"
