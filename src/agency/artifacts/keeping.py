"""Conservare una versione e dire da dove viene; ritrovarla; accorgersi se si è guastata.

L'ordine è sempre lo stesso: prima il contenuto nel deposito, poi la riga nel registro, poi l'evento che
la usa (consegna, presentazione, giudizio). Così una riga dice sempre la verità su un contenuto che esiste,
e una ripresa a metà ripete il passo senza duplicare nulla.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from collections.abc import Mapping
from pathlib import Path

from agency.contracts.artifact import ArtifactMissing, ArtifactStore, Origin
from agency.ledger import Ledger
from agency.ledger.models import ArtifactRow
from agency.ledger.store import now

# Solo la tabella interna di Python: quella del sistema cambia da macchina a macchina.
TYPES = mimetypes.MimeTypes()
UNKNOWN = "application/octet-stream"
MIN_PREFIX = 8
CHUNK = 1 << 20
HEX = re.compile(r"[0-9a-f]+")


class CannotRestore(Exception):
    """La versione chiesta non si può ripristinare: il motivo è nel messaggio."""


def media_type(path: str) -> str:
    return TYPES.guess_type(path, strict=True)[0] or UNKNOWN


def keep(
    store: ArtifactStore,
    ledger: Ledger,
    files: Mapping[str, Path],
    *,
    project: str,
    origin: Origin,
    ticket_id: str,
    run: int | None,
) -> dict[str, str]:
    """`files` va dal percorso da registrare al file da conservare. Restituisce gli hash conservati."""
    rows: list[ArtifactRow] = []
    for path, source in files.items():
        blob = store.put(source)
        rows.append(
            ArtifactRow(
                at=now(),
                sha256=blob.sha256,
                project=project,
                path=path,
                ticket_id=ticket_id,
                origin=origin.value,
                run=run,
                media_type=media_type(path),
                size=blob.size,
            )
        )
    ledger.record_artifacts(rows)
    return {row.path: row.sha256 for row in rows}


def find(ledger: Ledger, prefix: str) -> list[ArtifactRow]:
    """Le righe della sola versione che inizia così. Un prefisso corto o ambiguo non vale."""
    prefix = prefix.strip().lower()
    if not HEX.fullmatch(prefix):
        raise CannotRestore("l'hash è esadecimale: solo cifre e lettere da a a f")
    if len(prefix) < MIN_PREFIX:
        raise CannotRestore(f"servono almeno {MIN_PREFIX} cifre dell'hash")
    rows = ledger.artifacts_with(prefix)
    versions = {row.sha256 for row in rows}
    if not versions:
        raise CannotRestore(f"nessuna versione conservata ha un hash che inizia con {prefix}")
    if len(versions) > 1:
        raise CannotRestore(f"hash ambiguo: {prefix} vale per {len(versions)} versioni, aggiungi cifre")
    return rows


def restore(store: ArtifactStore, ledger: Ledger, prefix: str, destination: Path) -> list[ArtifactRow]:
    """Copia la versione in un file nuovo. Non sovrascrive mai: il file che c'è potrebbe essere l'unico."""
    rows = find(ledger, prefix)
    digest = rows[0].sha256
    # Prima la versione, poi la destinazione: se la versione manca, non resta un file vuoto.
    try:
        original = store.open(digest)
    except ArtifactMissing:
        raise CannotRestore(
            f"la versione {digest[:12]} manca dal deposito: agency verify dice quali"
        ) from None
    with original:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Creazione esclusiva: nessuna corsa con chi scrive nello stesso posto nello stesso momento.
        try:
            copy = destination.open("xb")
        except FileExistsError:
            raise CannotRestore(f"{destination} esiste già: il ripristino non sovrascrive") from None
        check = hashlib.sha256()
        with copy:
            while chunk := original.read(CHUNK):
                check.update(chunk)
                copy.write(chunk)
    if check.hexdigest() != digest:
        destination.unlink()
        raise CannotRestore(f"la versione {digest[:12]} nel deposito è danneggiata: agency verify dice quali")
    return rows


def damaged(store: ArtifactStore, ledger: Ledger) -> list[ArtifactRow]:
    """Le righe le cui versioni mancano dal deposito o non hanno più il loro hash."""
    rows = ledger.all_artifacts()
    broken = {digest for digest in {row.sha256 for row in rows} if not store.intact(digest)}
    return [row for row in rows if row.sha256 in broken]


def versions(ledger: Ledger) -> int:
    return len({row.sha256 for row in ledger.all_artifacts()})
