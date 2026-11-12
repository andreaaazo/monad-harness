"""No-follow file helpers confined to a work folder, and the hash of a file the harness trusts."""

from __future__ import annotations

import errno
import fnmatch
import hashlib
import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath


class OutsidePerimeter(Exception):
    """A path the harness refuses: outside the work folder, through a link, not a regular file, or too big."""


# What the harness reads whole from a file the sandbox wrote (it can write a file of up to 2 GiB), for the
# callers that pass a `limit` to `read_under`: text and JSON it parses, an image it decodes, a Craft document.
MAX_TEXT_FILE_BYTES = 8 * 2**20
MAX_IMAGE_FILE_BYTES = 64 * 2**20
MAX_DOCUMENT_BYTES = 256 * 2**20


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
    """Opens the file without following a link and without waiting on a FIFO or a device.

    The last component is opened with O_NONBLOCK, so a FIFO the sandbox planted opens at once; a file opened
    for reading is then refused unless it is a regular file. O_NONBLOCK is cleared before the descriptor
    goes back, so the caller reads and writes as it always did. A folder opened with O_DIRECTORY is fine.
    """
    with _parent(root, relative) as (directory, name):
        try:
            descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=directory)
        except OSError as error:
            _refuse_a_link(directory, name, relative, error)
            raise
    try:
        reads = flags & os.O_ACCMODE != os.O_WRONLY and not flags & os.O_DIRECTORY
        if reads and not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OutsidePerimeter(f"{relative} non è un file")
        os.set_blocking(descriptor, True)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def ensure_dir_under(root: Path, relative: str) -> None:
    """Creates every missing folder of `relative`, like `mkdir -p`, and refuses one that is a symlink."""
    with _parent(root, relative, create=True) as (directory, name):
        with suppress(FileExistsError):
            os.mkdir(name, dir_fd=directory)
        os.close(_enter(directory, name, relative))


def read_under(root: Path, relative: str, limit: int | None = None) -> bytes:
    """The file's bytes. With a `limit`, it reads at most one byte past it and refuses a larger file."""
    with os.fdopen(open_under(root, relative, os.O_RDONLY), "rb") as handle:
        data = handle.read() if limit is None else handle.read(limit + 1)
    if limit is not None and len(data) > limit:
        raise OutsidePerimeter(f"{relative}: supera il limite di {limit // 2**20} MiB")
    return data


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


def file_sha256(path: Path) -> str:
    """The file's sha256. It follows links: on a path the sandbox can write, use `sha256_under`."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def is_file_under(root: Path, relative: str) -> bool:
    """True for a regular file, reached without following any link: a link, a folder or a gap is False."""
    _parts(relative)
    try:
        with _parent(root, relative) as (directory, name):
            return stat.S_ISREG(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode)
    except (OutsidePerimeter, OSError):
        return False


_MAGIC = "*?["


def _listing(directory: int) -> list[str]:
    try:
        return os.listdir(directory)
    except OSError:
        return []


def _kind(directory: int, name: str) -> int:
    try:
        return stat.S_IFMT(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode)
    except OSError:
        return 0


def _matching(directory: int, pattern: str) -> list[str]:
    """The names a path component matches; like `glob`, a wildcard never matches a hidden name."""
    if not any(char in pattern for char in _MAGIC):
        return [pattern]
    hidden = pattern.startswith(".")
    return [
        name
        for name in _listing(directory)
        if (hidden or not name.startswith(".")) and fnmatch.fnmatchcase(name, pattern)
    ]


def _descend(
    directory: int, name: str, prefix: tuple[str, ...], parts: tuple[str, ...], found: set[str]
) -> None:
    if _kind(directory, name) != stat.S_IFDIR:
        return
    try:
        inner = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
    except OSError:
        return
    try:
        _walk(inner, (*prefix, name), parts, found)
    finally:
        os.close(inner)


def _walk(directory: int, prefix: tuple[str, ...], parts: tuple[str, ...], found: set[str]) -> None:
    head, *rest = parts
    if head == "**":
        if rest:
            _walk(directory, prefix, tuple(rest), found)
        for name in _listing(directory):
            if name.startswith("."):
                continue
            if not rest and _kind(directory, name) == stat.S_IFREG:
                found.add("/".join((*prefix, name)))
            _descend(directory, name, prefix, parts, found)
        return
    for name in _matching(directory, head):
        if rest:
            _descend(directory, name, prefix, tuple(rest), found)
        elif _kind(directory, name) == stat.S_IFREG:
            found.add("/".join((*prefix, name)))


def glob_under(root: Path, pattern: str) -> list[str]:
    """The regular files under `root` that the pattern matches, as sorted relative POSIX paths.

    Matches by component like `glob.glob(recursive=True)`, `**` included. It never enters a folder that is a
    link and never lists a link, so the names of a linked host folder cannot come out. A pattern that leaves
    `root` matches nothing.
    """
    try:
        parts = _parts(pattern)
        top = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    except (OutsidePerimeter, OSError):
        return []
    found: set[str] = set()
    try:
        _walk(top, (), parts, found)
    finally:
        os.close(top)
    return sorted(found)


def inside(work: Path, relative: str) -> Path:
    """`work / relative` with every link resolved, or `OutsidePerimeter` when that lands outside `work`."""
    target = (work / relative).resolve()
    root = work.resolve()
    if target != root and root not in target.parents:
        raise OutsidePerimeter(f"{relative} è fuori dalla cartella del lavoro")
    return target
