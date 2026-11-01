"""Percorsi e hash dentro il perimetro del lavoro."""

from __future__ import annotations

import hashlib
from pathlib import Path


class OutsidePerimeter(Exception):
    """Il percorso esce dalla cartella del lavoro."""


def inside(work: Path, relative: str) -> Path:
    target = (work / relative).resolve()
    root = work.resolve()
    if target != root and root not in target.parents:
        raise OutsidePerimeter(f"{relative} è fuori dalla cartella del lavoro")
    return target


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
