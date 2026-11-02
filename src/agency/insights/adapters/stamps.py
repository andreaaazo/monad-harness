"""L'impronta di un file sorgente: nome, dimensione e ora di modifica. Basta a capire se è cambiato."""

from __future__ import annotations

from pathlib import Path

from agency.insights.domain import SourceStamp


def stamp(path: Path) -> SourceStamp:
    try:
        status = path.stat()
    except FileNotFoundError:
        return SourceStamp(name=path.name, size=None, modified_ns=None)
    return SourceStamp(name=path.name, size=status.st_size, modified_ns=status.st_mtime_ns)
