"""Paths and hashes inside the work's perimeter: the no-follow helpers of `agency.contracts.files`,
re-exported for the tools, plus `sha256` and `clip`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from agency.contracts.files import (
    MAX_DOCUMENT_BYTES,
    MAX_IMAGE_FILE_BYTES,
    MAX_TEXT_FILE_BYTES,
    OutsidePerimeter,
    ensure_dir_under,
    glob_under,
    inside,
    is_file_under,
    open_under,
    read_under,
    replace_under,
    sha256_under,
    write_new_under,
)

__all__ = [
    "MAX_DOCUMENT_BYTES",
    "MAX_IMAGE_FILE_BYTES",
    "MAX_TEXT_FILE_BYTES",
    "OutsidePerimeter",
    "clip",
    "ensure_dir_under",
    "glob_under",
    "inside",
    "is_file_under",
    "open_under",
    "read_under",
    "replace_under",
    "sha256",
    "sha256_under",
    "write_new_under",
]


def sha256(path: Path) -> str:
    """The file's sha256, read in 1 MiB chunks. It follows links: on a path the sandbox can write, use
    `sha256_under`."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clip(text: str, limit: int = 4000) -> str:
    """Tool results stay short, since the detail is in the files: a long text keeps its start and its end."""
    if len(text) <= limit:
        return text
    head = limit * 3 // 4
    return f"{text[:head]}\n[… {len(text) - limit} caratteri omessi …]\n{text[-(limit - head) :]}"
