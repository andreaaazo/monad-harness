"""Keeping a version and saying where it comes from; finding it again; noticing when it is damaged.

The order never changes: the content into the store first, then its row in the registry, then the event that
uses it (delivery, presentation, judgment). So a row always tells the truth about a content that exists, and
a step interrupted halfway repeats on resume without duplicating anything.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from collections.abc import Mapping
from pathlib import Path

from agency.contracts.artifact import ArtifactMissing, ArtifactStore, Origin
from agency.contracts.files import OutsidePerimeter, ensure_dir_under, open_under
from agency.ledger import Ledger
from agency.ledger.models import ArtifactRow
from agency.ledger.store import now

# Python's built-in table only: the system's own table differs from machine to machine.
TYPES = mimetypes.MimeTypes()
UNKNOWN = "application/octet-stream"
MIN_PREFIX = 8
CHUNK = 1 << 20
HEX = re.compile(r"[0-9a-f]+")


class CannotRestore(Exception):
    """The requested version cannot be restored; the message, shown to the operator, says why."""


def media_type(path: str) -> str:
    """The MIME type a path's extension gives, the same on every machine."""
    return TYPES.guess_type(path, strict=True)[0] or UNKNOWN


def keep(
    store: ArtifactStore,
    ledger: Ledger,
    root: Path,
    files: Mapping[str, str],
    *,
    project: str,
    origin: Origin,
    ticket_id: str,
    run: int | None,
) -> dict[str, str]:
    """`files` maps the path to record to the file to keep. Returns the kept hashes, by recorded path."""
    rows: list[ArtifactRow] = []
    # Each source is a path relative to `root`. It is opened without following links, because the
    # sandbox may have swapped the file for one.
    for path, relative in files.items():
        with os.fdopen(open_under(root, relative, os.O_RDONLY), "rb") as source:
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
    """The rows of the one version whose hash starts with `prefix`. A short or ambiguous prefix is refused."""
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


def restore(
    store: ArtifactStore, ledger: Ledger, prefix: str, destination: Path, *, projects_dir: Path
) -> list[ArtifactRow]:
    """Copies the version into a new file. It never overwrites: a file already there may be the only copy
    of its content."""
    rows = find(ledger, prefix)
    digest = rows[0].sha256
    # The version first, then the destination: a missing version leaves no empty file behind.
    try:
        original = store.open(digest)
    except ArtifactMissing:
        raise CannotRestore(
            f"la versione {digest[:12]} manca dal deposito: agency verify dice quali"
        ) from None
    with original:
        _make_parents(destination, projects_dir)
        # Exclusive creation: no race with anyone writing the same path at the same moment.
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


def _make_parents(destination: Path, projects_dir: Path) -> None:
    """Creates the folders of `destination`; a link a sandbox left below the projects folder is refused.

    Elsewhere the path is the operator's own layout (a symlinked home, say) and links are followed.
    """
    parent = destination.absolute().parent
    for root in (projects_dir.absolute(), projects_dir.resolve()):
        if parent == root or root in parent.parents:
            parts = parent.relative_to(root).parts
            try:
                if parts:
                    ensure_dir_under(root, "/".join(parts))
                else:
                    root.mkdir(parents=True, exist_ok=True)
            except OutsidePerimeter as exc:
                raise CannotRestore(str(exc)) from exc
            return
    parent.mkdir(parents=True, exist_ok=True)


def damaged(store: ArtifactStore, ledger: Ledger) -> list[ArtifactRow]:
    """The rows whose versions are missing from the store or no longer hash to their name."""
    rows = ledger.all_artifacts()
    broken = {digest for digest in {row.sha256 for row in rows} if not store.intact(digest)}
    return [row for row in rows if row.sha256 in broken]


def versions(ledger: Ledger) -> int:
    """How many distinct contents the registry keeps."""
    return len({row.sha256 for row in ledger.all_artifacts()})
