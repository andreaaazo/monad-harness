"""The no-follow helpers for the files the harness opens under the work folder (SEC-001, Task 2.1)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from agency.tools import files
from agency.tools.files import OutsidePerimeter

Use = Callable[[Path, str], object]


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """A work folder with a real folder and a real file, each beside a symlink of that shape to the host."""
    root, host = tmp_path / "work", tmp_path / "host"
    (root / "real").mkdir(parents=True)
    host.mkdir()
    (root / "real" / "kept.txt").write_bytes(b"dentro")
    (root / "real.txt").write_bytes(b"dentro")
    (host / "kept.txt").write_bytes(b"fuori")
    (root / "link").symlink_to(host, target_is_directory=True)
    (root / "link.txt").symlink_to(host / "kept.txt")
    return root, host


def host_files(host: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in host.iterdir()}


def opened(root: Path, relative: str) -> bytes:
    descriptor = files.open_under(root, relative, os.O_RDONLY)
    try:
        return os.read(descriptor, 100)
    finally:
        os.close(descriptor)


def written_new(root: Path, folder: str) -> bytes:
    files.write_new_under(root, f"{folder}/new.txt", b"nuovo")
    return (root / folder / "new.txt").read_bytes()


def replaced(root: Path, folder: str) -> bytes:
    files.replace_under(root, f"{folder}/kept.txt", b"nuovo")
    return (root / folder / "kept.txt").read_bytes()


def ensured(root: Path, relative: str) -> bool:
    files.ensure_dir_under(root, relative)
    return (root / relative).is_dir()


DENTRO = hashlib.sha256(b"dentro").hexdigest()

# Each use takes the name of a real entry, or of the symlink of the same shape: "real" or "link".
USES: dict[str, tuple[Use, object]] = {
    "open_under": (lambda root, name: opened(root, f"{name}/kept.txt"), b"dentro"),
    "read_under": (lambda root, name: files.read_under(root, f"{name}/kept.txt"), b"dentro"),
    "sha256_under": (lambda root, name: files.sha256_under(root, f"{name}/kept.txt"), DENTRO),
    "write_new_under": (written_new, b"nuovo"),
    "replace_under": (replaced, b"nuovo"),
    "ensure_dir_under, last component": (ensured, True),
    "ensure_dir_under, inner component": (lambda root, name: ensured(root, f"{name}/sub"), True),
    "open_under, last component": (lambda root, name: opened(root, f"{name}.txt"), b"dentro"),
    "read_under, last component": (lambda root, name: files.read_under(root, f"{name}.txt"), b"dentro"),
    "sha256_under, last component": (lambda root, name: files.sha256_under(root, f"{name}.txt"), DENTRO),
}


@pytest.mark.parametrize("use", USES)
def test_a_symlinked_directory_component_is_refused(tree: tuple[Path, Path], use: str) -> None:
    root, host = tree
    call, expected = USES[use]
    assert call(root, "real") == expected  # the same call works where nothing is a link

    with pytest.raises(OutsidePerimeter):
        call(root, "link")

    assert host_files(host) == {"kept.txt": b"fuori"}


HELPERS: dict[str, Use] = {
    "open_under": opened,
    "read_under": files.read_under,
    "sha256_under": files.sha256_under,
    "write_new_under": lambda root, relative: files.write_new_under(root, relative, b"nuovo"),
    "replace_under": lambda root, relative: files.replace_under(root, relative, b"nuovo"),
    "ensure_dir_under": files.ensure_dir_under,
}


@pytest.mark.parametrize("helper", HELPERS)
@pytest.mark.parametrize(
    "relative",
    [
        "../host/kept.txt",
        "real/../../host/kept.txt",
        "real/../real/kept.txt",
        "{host}/kept.txt",
        "/{host}/kept.txt",
    ],
)
def test_dotdot_and_absolute_paths_are_refused(tree: tuple[Path, Path], helper: str, relative: str) -> None:
    root, host = tree

    with pytest.raises(OutsidePerimeter):
        HELPERS[helper](root, relative.format(host=host))

    assert host_files(host) == {"kept.txt": b"fuori"}
    assert (root / "real" / "kept.txt").read_bytes() == b"dentro"


def test_write_new_under_refuses_an_existing_file(tree: tuple[Path, Path]) -> None:
    root, host = tree
    (root / "real" / "dangling.txt").symlink_to(host / "absent.txt")
    files.write_new_under(root, "real/new.txt", b"primo")

    for taken in ["real/new.txt", "real/kept.txt", "link.txt", "real/dangling.txt"]:
        with pytest.raises(FileExistsError):
            files.write_new_under(root, taken, b"secondo")

    assert (root / "real" / "new.txt").read_bytes() == b"primo"
    assert (root / "real" / "kept.txt").read_bytes() == b"dentro"
    assert host_files(host) == {"kept.txt": b"fuori"}
