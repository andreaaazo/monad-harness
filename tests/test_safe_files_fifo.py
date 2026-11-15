"""A FIFO planted where the harness reads: the open must not wait for a writer."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from agency.ledger import Ledger
from agency.workshop import files, render
from agency.workshop.files import OutsidePerimeter
from agency.workshop.sandbox import Sandbox
from support.safe_files import returns_within

FIFO_READERS: dict[str, Callable[[Path, str], object]] = {
    "read_under": files.read_under,
    "read_under with a limit": lambda root, relative: files.read_under(root, relative, 2**20),
    "sha256_under": files.sha256_under,
    "open_under": lambda root, relative: os.close(files.open_under(root, relative, os.O_RDONLY)),
}


@pytest.mark.parametrize("reader", FIFO_READERS)
def test_a_planted_fifo_is_refused_at_once(fifo_tree: tuple[Path, Path], reader: str) -> None:
    work, fifo = fifo_tree
    error = returns_within(5, lambda: FIFO_READERS[reader](work, "real/trappola.png"), fifo)
    assert isinstance(error, OutsidePerimeter)
    assert str(error) == "real/trappola.png non è un file"


def test_render_does_not_wait_for_a_planted_fifo(fifo_tree: tuple[Path, Path]) -> None:
    work, fifo = fifo_tree
    ledger = Ledger(work.parent / "l.sqlite")
    error = returns_within(
        5, lambda: render.render_one(Sandbox(work), ledger, "p", "real/trappola.png"), fifo
    )
    assert isinstance(error, OutsidePerimeter)


def test_a_folder_is_not_a_file_to_read(tree: tuple[Path, Path]) -> None:
    root, _ = tree
    with pytest.raises(OutsidePerimeter, match="real non è un file"):
        files.read_under(root, "real")


def test_open_under_hands_back_a_blocking_descriptor_of_the_file(tree: tuple[Path, Path]) -> None:
    """O_NONBLOCK is for the open only: a read of a regular file, or a write, goes on as it always did."""
    root, _ = tree
    descriptor = files.open_under(root, "real.txt", os.O_RDONLY)
    try:
        assert os.get_blocking(descriptor)
    finally:
        os.close(descriptor)
    descriptor = files.open_under(root, "new.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        assert os.get_blocking(descriptor)
    finally:
        os.close(descriptor)


def test_open_under_still_opens_a_folder_with_o_directory(tree: tuple[Path, Path]) -> None:
    root, _ = tree
    descriptor = files.open_under(root, "real", os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert stat.S_ISDIR(os.fstat(descriptor).st_mode)
    finally:
        os.close(descriptor)
