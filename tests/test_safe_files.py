"""The no-follow helpers for the files the harness opens under the work folder (SEC-001, Task 2.1)."""

from __future__ import annotations

import hashlib
import io
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from agency.artifacts import FileStore
from agency.contracts.artifact import Origin
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.qa import delivery
from agency.tools import board, files, presentation, render, surface
from agency.tools.craft import CommandIndex
from agency.tools.files import OutsidePerimeter
from agency.tools.sandbox import Sandbox

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


# The readers that open work files (Task 2.2). The host folder holds the sentinel: a red image and an SVG
# that only the host has. The sandbox leaves a link to it where a reader looks.

RED = (200, 0, 0)
SECRET_SVG = b"<svg>solo l'host lo ha</svg>"
SEGNO = TicketSpec(
    title="Segno",
    request="Disegna il segno",
    type=TicketType.PRODUCTION,
    sender="design-director",
    assignee="identity-designer",
    outputs=["exports/segno.svg"],
    checks={"*.svg": ["svg_audit"]},
    media=[Medium.NONE],
    medium_why="verifica del solo file, senza master",
)
Read = Callable[[], object]


def png(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


def shows_red(data: bytes) -> bool:
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
    return RED in {color for _, color in rgb.getcolors(rgb.width * rgb.height) or []}


def tool_context(work: Path) -> surface.ToolContext:
    ledger, store = Ledger(work.parent / "l.sqlite"), FileStore(work.parent / "artifacts")
    return surface.ToolContext("critic", "p", "T-1", "i", ledger, Sandbox(work), CommandIndex([]), store)


def rendering(work: Path, host: Path) -> Read:
    (work / "exports").symlink_to(host, target_is_directory=True)
    ledger = Ledger(work.parent / "l.sqlite")
    return lambda: render.render_one(Sandbox(work), ledger, "p", "exports/secret.png")


def viewing(work: Path, host: Path) -> Read:
    (work / "segno.png").symlink_to(host / "secret.png")
    ctx = tool_context(work)
    return lambda: surface.view_image(ctx, surface.ViewImage(path="segno.png"), "op1")


def presenting(work: Path, host: Path) -> Read:
    """SEC-003's shape: a hidden link beside the delivered application."""
    folder = work / "proposals/r1/v"
    (folder / "applicazioni-v").mkdir(parents=True)
    (folder / "proposta-v.png").write_bytes(png((20, 20, 20)))
    (folder / "applicazioni-v/insegna.png").write_bytes(png((240, 240, 240)))
    (folder / "applicazioni-v/.zz.png").symlink_to(host / "secret.png")
    mark, applications = presentation.proposal_files(
        work, 1, "V", ["applicazioni-v/insegna.png", "applicazioni-v/.zz.png"]
    )
    item = presentation.Proposal("V", "Il merlo", "L'idea", "Perché", "Il limite", mark, applications)
    return lambda: presentation.build([item], "V", "Regge meglio", work / "presentation/r1")


def accepting(work: Path, host: Path) -> Read:
    """The delivered digest is the host file's: reading through the link would match it."""
    ledger = Ledger(work.parent / "l.sqlite")
    ticket = ledger.open(SEGNO, "p")
    digest = hashlib.sha256(SECRET_SVG).hexdigest()
    ledger.apply(ticket, Action.DELIVER, "identity-designer", "consegna", None, {"exports/segno.svg": digest})
    (work / "exports").symlink_to(host, target_is_directory=True)
    return lambda: delivery.acceptance_problems(ledger, "p", Sandbox(work), ticket)


def boarding(work: Path, host: Path) -> Read:
    sketch = work / "explorations/r1/a/schizzo-a.png"
    sketch.parent.mkdir(parents=True)
    sketch.symlink_to(host / "secret.png")
    return lambda: board.build([("V", sketch)], work / "board/r1/tavola.png")


def keeping(work: Path, host: Path) -> Read:
    """`ToolContext.keep` on a delivered file that the sandbox swapped for a link to the host's file."""
    (work / "segno.svg").symlink_to(host / "segno.svg")
    ctx = tool_context(work)
    return lambda: ctx.keep(["segno.svg"], Origin.DELIVERY)


READERS: dict[str, tuple[Callable[[Path, Path], Read], type[Exception]]] = {
    "render_one": (rendering, OutsidePerimeter),
    "view_image": (viewing, OutsidePerimeter),
    "presentation image reader": (presenting, OutsidePerimeter),
    "delivery hashing": (accepting, OutsidePerimeter),
    "board.build": (boarding, OutsidePerimeter),
    "keeping": (keeping, OutsidePerimeter),
}


def outputs(work: Path) -> list[Path]:
    """The regular files under the work folder, without going through a link."""
    return [path for path in work.rglob("*") if path.is_file() and not path.is_symlink()]


@pytest.mark.parametrize("reader", READERS)
def test_harness_readers_refuse_a_planted_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str
) -> None:
    """The reader refuses the link without opening the host's file, and nothing reaches the host or the work.

    The sandbox can swap a file for a link right after `inside()` has looked. To stand for that moment, the
    test plants the link first and makes `Path.resolve` blind to links, so `inside()` sees the tree as it was
    before the swap. Readers that open the path without checking it first follow the link anyway. During the
    call the host's files are unreadable: a reader that opened one would fail with PermissionError instead.
    """
    work, host = tmp_path / "work", tmp_path / "host"
    work.mkdir()
    host.mkdir()
    (host / "secret.png").write_bytes(png(RED))
    (host / "segno.svg").write_bytes(SECRET_SVG)
    prepare, refusal = READERS[reader]
    read = prepare(work, host)
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: Path(os.path.abspath(self)))
    for sentinel in host.iterdir():
        sentinel.chmod(0)

    try:
        with pytest.raises(refusal):
            read()
    finally:
        for sentinel in host.iterdir():
            sentinel.chmod(0o600)
        monkeypatch.undo()

    assert host_files(host) == {"secret.png": png(RED), "segno.svg": SECRET_SVG}
    for path in outputs(work):
        data = path.read_bytes()
        assert SECRET_SVG not in data
        assert not (path.suffix == ".png" and shows_red(data)), path
