"""Percorsi e hash dentro il perimetro del lavoro."""

from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath


class OutsidePerimeter(Exception):
    """Il percorso esce dalla cartella del lavoro."""


# The helpers below never follow a symlink under `root`, which the caller trusts. The sandbox can write the
# work folder, so it can swap any folder there for a link to a host folder. Each helper therefore opens
# `root`, then every component of `relative` through the descriptor of the one before, with O_NOFOLLOW.
# Resolving the path first and opening it afterwards would leave a window in which the tree can change.


def _parts(relative: str) -> tuple[str, ...]:
    path = PurePosixPath(relative)
    parts = path.parts
    if not parts or path.is_absolute() or ".." in parts:
        raise OutsidePerimeter(f"{relative} è fuori dalla cartella del lavoro")
    return parts


def _refuse_a_link(directory: int, name: str, relative: str, error: OSError) -> None:
    """O_NOFOLLOW fails on a symlink with ELOOP, or ENOTDIR with O_DIRECTORY: tell it from a real error."""
    if error.errno in (errno.ELOOP, errno.ENOTDIR):
        with suppress(OSError):
            if stat.S_ISLNK(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode):
                raise OutsidePerimeter(f"{relative} è fuori dalla cartella del lavoro") from error


def _enter(directory: int, name: str, relative: str) -> int:
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
    except OSError as error:
        _refuse_a_link(directory, name, relative, error)
        raise


@contextmanager
def _parent(root: Path, relative: str, create: bool = False) -> Iterator[tuple[int, str]]:
    """The descriptor of the folder that holds the last component, and that component's name."""
    *folders, name = _parts(relative)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for folder in folders:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(folder, dir_fd=directory)
            inner = _enter(directory, folder, relative)
            os.close(directory)
            directory = inner
        yield directory, name
    finally:
        os.close(directory)


def open_under(root: Path, relative: str, flags: int, mode: int = 0o600) -> int:
    with _parent(root, relative) as (directory, name):
        try:
            return os.open(name, flags | os.O_NOFOLLOW, mode, dir_fd=directory)
        except OSError as error:
            _refuse_a_link(directory, name, relative, error)
            raise


def ensure_dir_under(root: Path, relative: str) -> None:
    """Creates every missing folder of `relative`, like `mkdir -p`, and refuses one that is a symlink."""
    with _parent(root, relative, create=True) as (directory, name):
        with suppress(FileExistsError):
            os.mkdir(name, dir_fd=directory)
        os.close(_enter(directory, name, relative))


def read_under(root: Path, relative: str) -> bytes:
    with os.fdopen(open_under(root, relative, os.O_RDONLY), "rb") as handle:
        return handle.read()


def write_new_under(root: Path, relative: str, data: bytes) -> None:
    """Creates the file, and refuses one that exists already, a symlink included."""
    with os.fdopen(open_under(root, relative, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as handle:
        handle.write(data)


def replace_under(root: Path, relative: str, data: bytes) -> None:
    """Writes the data beside the file and renames it over the file: a reader sees the old or the new one."""
    with _parent(root, relative) as (directory, name):
        temporary = f".{name}.{secrets.token_hex(8)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        try:
            with os.fdopen(os.open(temporary, flags, 0o600, dir_fd=directory), "wb") as handle:
                handle.write(data)
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory)
            raise


def sha256_under(root: Path, relative: str) -> str:
    with os.fdopen(open_under(root, relative, os.O_RDONLY), "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


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
