"""Links in the work folder: the Craft runner and the file helpers never follow them (Tasks 2.F12, 2.F17)."""

from __future__ import annotations

import glob
import json
import os
import stat
from pathlib import Path

import pytest

from agency.contracts import files
from agency.tools import craft
from agency.tools.craft import Command, CommandIndex
from agency.tools.files import OutsidePerimeter, glob_under, is_file_under
from agency.tools.sandbox import JOB, Completed, Sandbox

DOCUMENT = "source/segno.vectorcraft"
STEPS = [{"command": "path.create"}]
INDEX = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])


class RecordingSandbox(Sandbox):
    """Plays `vectorcraft-cli run`: writes the exported document and keeps the command it was given."""

    def __init__(self, work: Path, ops: Path) -> None:
        super().__init__(work, ops=ops)
        self.calls: list[list[str]] = []

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        self.calls.append(command)
        export = Path(command[command.index("--export") + 1]).relative_to(JOB)
        (self.work / export).write_text("documento costruito", encoding="utf-8")
        return Completed(0, json.dumps({"step": "cmd", "result": {"id": 2}}), "")


def craft_folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    work, inputs, records = tmp_path / "work", tmp_path / "inputs", tmp_path / "records"
    for folder in (work / "source", inputs, records):
        folder.mkdir(parents=True)
    return work, inputs, records


def run_craft(work: Path, inputs: Path, records: Path) -> list[str]:
    sandbox = RecordingSandbox(work, inputs)
    craft.run_steps(sandbox, INDEX, DOCUMENT, STEPS, "op1", records)
    return sandbox.calls[0]


# The runner decides whether the CLI gets `--in` without looking through a link (2.F12)


def test_the_cli_gets_the_input_document_when_it_is_a_regular_file(tmp_path: Path) -> None:
    work, inputs, records = craft_folders(tmp_path)
    (work / DOCUMENT).write_text("documento", encoding="utf-8")
    command = run_craft(work, inputs, records)
    assert command[command.index("--in") + 1] == f"{JOB}/{DOCUMENT}"


def test_the_cli_gets_no_input_when_the_document_is_a_link(tmp_path: Path) -> None:
    """The link stays inside the work folder, so `inside()` lets it by: only a no-follow check refuses it."""
    work, inputs, records = craft_folders(tmp_path)
    (work / "kept.vectorcraft").write_text("altro documento", encoding="utf-8")
    (work / DOCUMENT).symlink_to(work / "kept.vectorcraft")
    command = run_craft(work, inputs, records)
    assert "--in" not in command
    assert (work / "kept.vectorcraft").read_text(encoding="utf-8") == "altro documento"


def test_the_cli_gets_no_input_when_the_document_is_a_folder(tmp_path: Path) -> None:
    work, inputs, records = craft_folders(tmp_path)
    (work / DOCUMENT).mkdir()
    sandbox = RecordingSandbox(work, inputs)
    with pytest.raises(IsADirectoryError):  # the copy back cannot replace a folder; the run itself happened
        craft.run_steps(sandbox, INDEX, DOCUMENT, STEPS, "op1", records)
    assert "--in" not in sandbox.calls[0]


# is_file_under: a regular file reached with no link on the way


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    root, host = tmp_path / "work", tmp_path / "host"
    (root / "real").mkdir(parents=True)
    host.mkdir()
    (root / "real/kept.txt").write_bytes(b"dentro")
    (root / "real.txt").write_bytes(b"dentro")
    (host / "kept.txt").write_bytes(b"fuori")
    (root / "link").symlink_to(host, target_is_directory=True)
    (root / "link.txt").symlink_to(host / "kept.txt")
    (root / "inner.txt").symlink_to(root / "real.txt")
    (root / "dangling.txt").symlink_to(host / "absent.txt")
    os.mkfifo(root / "pipe")
    return root, host


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("real.txt", True),
        ("real/kept.txt", True),
        ("link.txt", False),
        ("inner.txt", False),
        ("dangling.txt", False),
        ("link/kept.txt", False),
        ("real", False),
        ("link", False),
        ("pipe", False),
        ("absent.txt", False),
        ("real/absent.txt", False),
        ("absent/kept.txt", False),
        ("real.txt/kept.txt", False),
    ],
)
def test_is_file_under(tree: tuple[Path, Path], relative: str, expected: bool) -> None:
    root, host = tree
    assert is_file_under(root, relative) is expected
    assert (host / "kept.txt").read_bytes() == b"fuori"


@pytest.mark.parametrize("relative", ["../work/real.txt", "/etc/passwd", ""])
def test_is_file_under_refuses_a_path_that_leaves_the_folder(tree: tuple[Path, Path], relative: str) -> None:
    with pytest.raises(OutsidePerimeter):
        is_file_under(tree[0], relative)


# glob_under: the regular files a pattern matches, without entering a linked folder (2.F17, 2.F18)


@pytest.fixture
def plain(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    for name in (
        "a.svg",
        "b.png",
        ".hidden.svg",
        "exports/c.svg",
        "exports/deep/d.svg",
        "exports/deep/e.png",
        "exports/.dot/f.svg",
        "[x]/g.svg",
        "other/h.svg",
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(name)
    return root


@pytest.mark.parametrize(
    "pattern",
    [
        "a.svg",
        "*.svg",
        "*",
        "exports/*",
        "exports/*.svg",
        "exports/**",
        "exports/**/*.svg",
        "**/*.svg",
        "**/d.svg",
        "**",
        "*/*.svg",
        "exp*/d?p/*.png",
        ".hidden.svg",
        ".*",
        "exports/.dot/*",
        "[[]x]/*.svg",
        "[ab].*",
        "nothing/*",
        "a.svg/x",
    ],
)
def test_glob_under_matches_what_glob_does_on_a_tree_without_links(plain: Path, pattern: str) -> None:
    wanted = sorted(
        str(Path(path).relative_to(plain))
        for path in glob.glob(str(plain / pattern), recursive=True)
        if Path(path).is_file()
    )
    assert glob_under(plain, pattern) == wanted


def test_glob_under_skips_links_and_never_enters_a_linked_folder(tmp_path: Path) -> None:
    root, host = tmp_path / "work", tmp_path / "host"
    (root / "exports").mkdir(parents=True)
    (root / "real").mkdir()
    host.mkdir()
    (root / "real/ok.svg").write_text("dentro")
    (host / "secret.svg").write_text("fuori")
    (root / "exports").rmdir()
    (root / "exports").symlink_to(host, target_is_directory=True)
    (root / "real/linked.svg").symlink_to(host / "secret.svg")
    (root / "real/folder").symlink_to(host, target_is_directory=True)
    assert glob_under(root, "exports/*.svg") == []
    assert glob_under(root, "exports/**") == []
    assert glob_under(root, "**/*.svg") == ["real/ok.svg"]
    assert glob_under(root, "real/*") == ["real/ok.svg"]
    assert glob_under(root, "real/folder/*") == []
    assert glob_under(root, "real/linked.svg") == []
    assert (host / "secret.svg").read_text() == "fuori"


@pytest.mark.parametrize("pattern", ["../*", "/etc/*", "real/../../*", ""])
def test_glob_under_matches_nothing_outside_the_folder(tmp_path: Path, pattern: str) -> None:
    root = tmp_path / "work"
    root.mkdir()
    (tmp_path / "outside.svg").write_text("fuori")
    assert glob_under(root, pattern) == []


def test_glob_under_of_a_missing_root_is_empty(tmp_path: Path) -> None:
    assert glob_under(tmp_path / "absent", "*") == []


def test_glob_under_refuses_a_folder_that_became_a_link_after_the_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kind of `exports` was read as a folder; by the time it is opened it is a link to the host."""
    root, host = tmp_path / "work", tmp_path / "host"
    root.mkdir()
    host.mkdir()
    (host / "secret.svg").write_text("fuori")
    (root / "exports").symlink_to(host, target_is_directory=True)
    kind = files._kind
    monkeypatch.setattr(files, "_kind", lambda d, name: stat.S_IFDIR if name == "exports" else kind(d, name))
    assert glob_under(root, "exports/*.svg") == []
    assert glob_under(root, "**/*.svg") == []
