"""Paths and hashes inside the work's perimeter: the helpers of `agency.contracts.files`, re-exported for the
tools (`sha256` is its `file_sha256`), plus `clip`.
"""

from __future__ import annotations

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
)
from agency.contracts.files import (
    file_sha256 as sha256,
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
]


def clip(text: str, limit: int = 4000) -> str:
    """Tool results stay short, since the detail is in the files: a long text keeps its start and its end."""
    if len(text) <= limit:
        return text
    head = limit * 3 // 4
    return f"{text[:head]}\n[… {len(text) - limit} caratteri omessi …]\n{text[-(limit - head) :]}"
