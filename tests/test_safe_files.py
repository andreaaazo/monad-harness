"""The no-follow helpers for the files the harness opens under the work folder (SEC-001, Task 2.1)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import threading
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from PIL import Image

from agency import runtime
from agency.agents.loop import AgentRunner
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts import files as contract_files
from agency.contracts.artifact import Origin
from agency.contracts.concept import ConceptCard
from agency.contracts.gate import Decision
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.gateway import ModelGateway
from agency.graph import workflow
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow
from agency.qa import delivery
from agency.runtime import Session
from agency.tools import board, craft, files, presentation, render, surface
from agency.tools.craft import Command, CommandIndex
from agency.tools.files import OutsidePerimeter
from agency.tools.sandbox import JOB, Completed, Sandbox
from agency.tools.surface import PresentConcepts, ProposalText

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


# The graph nodes, the agent loop and `Session.start` (Task 2.F1-2.F7, 2.F22). The sandbox can leave a link in
# the work folder where the harness is about to read or write. A link at a folder, or at a file to read, is
# refused. A link at a file to write is replaced by the new file, and the host's file stays as it was.

SECRET = b"SEGRETO DELL'HOST"
PROJECT = "officina"
LETTER = "a"  # the explorer's letter; the anonymous one is "Z", and its proposal folder "z"
BRIEF = b"Un segno per un'officina"
MASTER = b"master del proposer"
CARD = ConceptCard(
    concept="Il merlo",
    client_fact="Fatto",
    why_not_obvious="Non ovvia",
    drawing="Un merlo",
    substitution="Solo lui",
)
TARGET = "source/master/segno.vectorcraft"
ROOT_SPEC = TicketSpec(
    title="Consegna",
    request="Un segno",
    type=TicketType.PRODUCTION,
    sender="router",
    assignee="identity-designer",
    outputs=[TARGET],
    checks={"*.vectorcraft": ["master_open"]},
    media=[Medium.VECTOR],
)
Plant = tuple[str, str]  # the path to turn into a link, and what it points to: a host file, or "" = the host


class Stop(Exception):
    """Raised by the stand-in graph and gateway: the code under test went on past the work folder."""


class Studio:
    """A project with a work folder, a ledger, the graph, and a host folder with files only the host has."""

    def __init__(self, tmp_path: Path) -> None:
        self.settings = Settings(
            data_dir=tmp_path / "data",
            projects_dir=tmp_path / "projects",
            _env_file=None,  # type: ignore[call-arg]
        )
        self.ledger = Ledger(tmp_path / "l.sqlite")
        runner = MagicMock()
        runner.run.return_value = Outcome(state=OutcomeState.BLOCKED, note="fermo")
        self.graph = workflow.build(runner, self.ledger, self.settings, InMemorySaver())
        self.work = self.settings.project_dir(parse_project_name(PROJECT)) / "work"
        self.work.mkdir(parents=True)
        self.host = tmp_path / "host"
        for name, data in {
            "secret.txt": SECRET,
            "secret.png": png(RED),
            "r1/presentazione.pdf": SECRET,
            "r1/applicazioni.json": SECRET,
            "r1/z/proposta-z.vectorcraft": SECRET,
        }.items():
            (self.host / name).parent.mkdir(parents=True, exist_ok=True)
            (self.host / name).write_bytes(data)
        self.before = snapshot(self.host)
        self.root = self.ledger.open(ROOT_SPEC, PROJECT)

    def node(self, name: str) -> Callable[[dict], dict]:
        return self.graph.nodes[name].bound.func  # type: ignore[attr-defined, no-any-return]

    def put(self, relative: str, data: bytes) -> None:
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def plant(self, where: str, points_to: str) -> None:
        """Turns `where` into a link: to the host folder, to a host file, or to nothing."""
        path = self.work / where
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(self.host / points_to if points_to else self.host)

    def concept(self, delivered: bool = False) -> None:
        spec = ROOT_SPEC.model_copy(
            update={
                "title": "Idea",
                "sender": "design-director",
                "outputs": [f"schizzo-{LETTER}.png"],
                "checks": {"*.png": ["visual_review"]},
            }
        )
        row = ConceptRow(
            project=PROJECT,
            round=1,
            letter=LETTER,
            lever="il nome",
            idea_ticket="",
            anon="Z",
            card_json=CARD.model_dump_json(),
            status="selezionata",
            sketch_file=f"explorations/r1/{LETTER}/schizzo-{LETTER}.png",
        )
        ticket = self.ledger.open(spec, PROJECT, concept=row)
        if delivered:
            self.ledger.apply(ticket, Action.DELIVER, "identity-designer", "consegna", None, {})

    def state(self) -> dict:
        return {"project": PROJECT, "root": self.root, "exploration": 1, "client_note": "", "chosen": "Z"}

    def explorers_work(self) -> None:
        self.put("brief.md", BRIEF)
        self.put(f"explorations/r1/{LETTER}/schizzo-{LETTER}.png", png((20, 20, 20)))
        self.put(f"explorations/r1/{LETTER}/foglio-{LETTER}.png", png((30, 30, 30)))
        self.put(f"explorations/r1/{LETTER}/scheda.json", CARD.model_dump_json().encode())
        self.put(
            "explorations/r1/applicazioni.json", json.dumps([{"name": "timbro", "size": "16 mm"}]).encode()
        )

    def proposer_work(self) -> None:
        self.put("proposals/r1/z/proposta-z.vectorcraft", MASTER)
        self.put("proposals/r1/z/proposta-z.png", png((40, 40, 40)))
        self.put("proposals/r1/z/scheda.json", CARD.model_dump_json().encode())

    def untouched(self) -> bool:
        return snapshot(self.host) == self.before


def snapshot(host: Path) -> dict[str, bytes | None]:
    return {
        str(item.relative_to(host)): item.read_bytes() if item.is_file() else None for item in host.rglob("*")
    }


def leaks(work: Path) -> bool:
    """Whether any regular file under the work folder holds the host's secret or the host's red image."""
    return any(
        SECRET in item.read_bytes() or (item.suffix == ".png" and shows_red(item.read_bytes()))
        for item in outputs(work)
    )


def link_after_write(monkeypatch: pytest.MonkeyPatch, module: ModuleType, name: str, target: Path) -> None:
    """The sandbox swaps the file for a link right after the harness wrote it and before it hashes it."""
    write = module.replace_under

    def wrapper(root: Path, relative: str, data: bytes) -> None:
        write(root, relative, data)
        if relative.endswith(name):
            (root / relative).unlink()
            (root / relative).symlink_to(target)

    monkeypatch.setattr(module, "replace_under", wrapper)


def refused(studio: Studio, run: Callable[[], object], planted: Plant) -> None:
    studio.plant(*planted)
    with pytest.raises(OutsidePerimeter):
        run()
    assert studio.untouched()
    assert not leaks(studio.work)


def overwrites(studio: Studio, run: Callable[[], object], planted: Plant) -> None:
    """The planted file link is replaced by the harness's own file; nothing reaches the host."""
    studio.plant(*planted)
    run()
    assert studio.untouched()
    assert not (studio.work / planted[0]).is_symlink()
    assert not leaks(studio.work)


def at(name: str) -> str:
    return f"explorations/r1/{LETTER}/{name}"


# make_board (2.F3)


def board_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept(delivered=True)
    studio.explorers_work()
    return studio


def test_the_board_node_copies_the_brief(tmp_path: Path) -> None:
    studio = board_studio(tmp_path)

    studio.node("make_board")(studio.state())

    assert (studio.work / "board/r1/brief.md").read_bytes() == BRIEF
    assert (studio.work / "board/r1/tavola.png").is_file()


def test_the_board_node_refuses_a_linked_brief(tmp_path: Path) -> None:
    studio = board_studio(tmp_path)
    refused(studio, lambda: studio.node("make_board")(studio.state()), ("brief.md", "secret.txt"))


def test_the_board_node_replaces_a_linked_brief_copy(tmp_path: Path) -> None:
    studio = board_studio(tmp_path)
    overwrites(studio, lambda: studio.node("make_board")(studio.state()), ("board/r1/brief.md", "secret.txt"))
    assert (studio.work / "board/r1/brief.md").read_bytes() == BRIEF


# select (2.F4)


def select_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.explorers_work()
    studio.put("board/r1/tavola.png", png((50, 50, 50)))
    return studio


def test_the_select_node_writes_the_cards_and_copies_the_sheets(tmp_path: Path) -> None:
    studio = select_studio(tmp_path)

    studio.node("select")(studio.state())

    assert "Il merlo" in (studio.work / "board/r1/schede.md").read_text(encoding="utf-8")
    assert (studio.work / "board/r1/fogli/Z.png").read_bytes() == (
        studio.work / at("foglio-a.png")
    ).read_bytes()


@pytest.mark.parametrize(
    "planted",
    [
        ("board/r1", ""),
        ("board/r1/fogli", ""),
        ("board/r1/fogli", "absent"),
        (at("foglio-a.png"), "secret.png"),
        (at("foglio-a.png"), "absent.png"),
    ],
)
def test_the_select_node_refuses_a_link(tmp_path: Path, planted: Plant) -> None:
    studio = select_studio(tmp_path)
    refused(studio, lambda: studio.node("select")(studio.state()), planted)


@pytest.mark.parametrize(
    "planted", [("board/r1/schede.md", "secret.txt"), ("board/r1/fogli/Z.png", "secret.txt")]
)
def test_the_select_node_replaces_a_linked_file_it_writes(tmp_path: Path, planted: Plant) -> None:
    studio = select_studio(tmp_path)
    overwrites(studio, lambda: studio.node("select")(studio.state()), planted)


# prepare_proposals (2.F5)


def proposals_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.explorers_work()
    return studio


def test_the_proposals_node_prepares_the_folder_and_opens_the_ticket(tmp_path: Path) -> None:
    studio = proposals_studio(tmp_path)

    studio.node("prepare_proposals")(studio.state())

    folder = studio.work / "proposals/r1/z"
    assert (folder / "brief.md").read_bytes() == BRIEF
    assert (folder / "schizzo.png").read_bytes() == (studio.work / at("schizzo-a.png")).read_bytes()
    (ticket,) = [t for t in studio.ledger.children(studio.root) if "Proposta" in studio.ledger.spec(t).title]
    digest = hashlib.sha256((folder / "schizzo.png").read_bytes()).hexdigest()
    assert studio.ledger.inputs(ticket)["schizzo.png"] == digest


@pytest.mark.parametrize(
    "planted",
    [
        ("explorations", ""),
        ("explorations/r1/applicazioni.json", "secret.txt"),
        ("brief.md", "secret.txt"),
        (at("scheda.json"), "secret.txt"),
        (at("schizzo-a.png"), "secret.png"),
        ("proposals/r1", ""),
        ("proposals/r1/z", ""),
    ],
)
def test_the_proposals_node_refuses_a_link(tmp_path: Path, planted: Plant) -> None:
    studio = proposals_studio(tmp_path)
    refused(studio, lambda: studio.node("prepare_proposals")(studio.state()), planted)
    assert studio.ledger.children(studio.root) == []


@pytest.mark.parametrize(
    "planted",
    [
        ("proposals/r1/z/brief.md", "secret.txt"),
        ("proposals/r1/z/scheda.json", "secret.txt"),
        ("proposals/r1/z/schizzo.png", "secret.png"),
    ],
)
def test_the_proposals_node_replaces_a_linked_file_it_writes(tmp_path: Path, planted: Plant) -> None:
    studio = proposals_studio(tmp_path)
    overwrites(studio, lambda: studio.node("prepare_proposals")(studio.state()), planted)


def test_the_proposals_node_refuses_an_input_swapped_for_a_link_before_it_is_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = proposals_studio(tmp_path)
    link_after_write(monkeypatch, workflow, "schizzo.png", studio.host / "secret.png")

    with pytest.raises(OutsidePerimeter):
        studio.node("prepare_proposals")(studio.state())

    assert studio.ledger.children(studio.root) == []


# present: the sheet of a proposal (2.F6)


def mark_of(studio: Studio) -> Path:
    studio.put("mark.png", png((20, 20, 20)))
    return studio.work / "mark.png"


def test_the_sheet_is_written_in_the_proposals_folder(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    output = studio.work / "proposals/r1/insieme-z.png"

    presentation.sheet(mark_of(studio), (), output)

    assert output.is_file()


@pytest.mark.parametrize("planted", [("proposals/r1", ""), ("proposals/r1", "absent")])
def test_the_sheet_refuses_a_linked_folder(tmp_path: Path, planted: Plant) -> None:
    studio = Studio(tmp_path)
    mark = mark_of(studio)
    refused(studio, lambda: presentation.sheet(mark, (), studio.work / "proposals/r1/insieme-z.png"), planted)


def test_the_sheet_replaces_a_linked_file(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    mark = mark_of(studio)
    overwrites(
        studio,
        lambda: presentation.sheet(mark, (), studio.work / "proposals/r1/insieme-z.png"),
        ("proposals/r1/insieme-z.png", "secret.png"),
    )


# start_production (2.F7)


def production_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.proposer_work()
    return studio


def test_the_production_node_copies_the_chosen_master(tmp_path: Path) -> None:
    studio = production_studio(tmp_path)

    studio.node("start_production")(studio.state())

    assert (studio.work / TARGET).read_bytes() == MASTER
    (ticket,) = [
        t for t in studio.ledger.children(studio.root) if "Rifinitura" in studio.ledger.spec(t).title
    ]
    assert set(studio.ledger.inputs(ticket)) == {
        "proposals/r1/z/scheda.json",
        "proposals/r1/z/proposta-z.png",
    }


@pytest.mark.parametrize(
    "planted",
    [
        ("proposals/r1/z/proposta-z.vectorcraft", "secret.txt"),
        ("proposals", ""),
        ("source", ""),
        ("source/master", ""),
        ("proposals/r1/z/proposta-z.png", "secret.png"),
        ("proposals/r1/z/scheda.json", "secret.txt"),
    ],
)
def test_the_production_node_refuses_a_link(tmp_path: Path, planted: Plant) -> None:
    studio = production_studio(tmp_path)
    refused(studio, lambda: studio.node("start_production")(studio.state()), planted)
    assert studio.ledger.children(studio.root) == []


def test_the_production_node_replaces_a_linked_target(tmp_path: Path) -> None:
    studio = production_studio(tmp_path)
    overwrites(studio, lambda: studio.node("start_production")(studio.state()), (TARGET, "secret.txt"))
    assert (studio.work / TARGET).read_bytes() == MASTER


# concept_gate (2.F22)


def gate_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Studio:
    studio = Studio(tmp_path)
    studio.put(presentation.pdf_of(1), b"%PDF- la presentazione")
    answer = Decision(approved=False, text="Ancora", choice="").model_dump()
    monkeypatch.setattr(workflow, "interrupt", lambda _: answer)
    return studio


def concept_state(studio: Studio) -> dict:
    proposal = ProposalText(letter="Z", title="Il merlo", idea="Idea", why="Perché", risk="Limite")
    note = PresentConcepts(proposals=[proposal], recommended="Z", reasons="Regge").model_dump_json()
    return studio.state() | {"client_note": note}


def test_the_concept_gate_records_the_hash_of_the_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = gate_studio(tmp_path, monkeypatch)

    studio.node("concept_gate")(concept_state(studio))

    (gate,) = studio.ledger.gates(PROJECT)
    digest = hashlib.sha256(b"%PDF- la presentazione").hexdigest()
    assert json.loads(gate.files_json) == {presentation.pdf_of(1): digest}


@pytest.mark.parametrize("planted", [("presentation", ""), (presentation.pdf_of(1), "secret.txt")])
def test_the_concept_gate_refuses_a_linked_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: Plant
) -> None:
    studio = gate_studio(tmp_path, monkeypatch)
    refused(studio, lambda: studio.node("concept_gate")(concept_state(studio)), planted)
    assert studio.ledger.gates(PROJECT) == []


# The agent loop (2.F1)


class Gateway:
    def call(self, *_: object) -> object:
        raise Stop

    def run(self, *_: object, **__: object) -> object:
        raise Stop


def runner_for(studio: Studio, workspace: str, tmp_path: Path) -> Callable[[], Outcome]:
    spec = ROOT_SPEC.model_copy(update={"workspace": workspace})
    ticket = studio.ledger.open(spec, PROJECT)
    gateway: ModelGateway = Gateway()  # type: ignore[assignment]
    runner = AgentRunner(gateway, studio.ledger, studio.settings, CommandIndex([]), FileStore(tmp_path / "a"))
    return lambda: runner.run(ticket)


@pytest.mark.parametrize("workspace", ["", "proposals/r1/a"])
def test_the_loop_creates_the_workspace_folder(tmp_path: Path, workspace: str) -> None:
    studio = Studio(tmp_path)

    with pytest.raises(Stop):
        runner_for(studio, workspace, tmp_path)()

    assert (studio.work / workspace).is_dir()


@pytest.mark.parametrize("planted", [("proposals", ""), ("proposals/r1", ""), ("proposals/r1/a", "")])
def test_the_loop_refuses_a_linked_workspace_before_the_sandbox_binds_it(
    tmp_path: Path, planted: Plant
) -> None:
    studio = Studio(tmp_path)
    refused(studio, runner_for(studio, "proposals/r1/a", tmp_path), planted)


# Session.start (2.F2)


class StopGraph:
    def invoke(self, *_: object) -> object:
        raise Stop


def started(studio: Studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], str]:
    monkeypatch.setattr(Session, "_record", lambda *_: None)
    brief = tmp_path / "brief.md"
    brief.write_bytes(BRIEF)
    session = Session(studio.settings, studio.ledger, StopGraph(), MagicMock(), MagicMock())  # type: ignore[arg-type]
    outputs_ = ["source/segno.vectorcraft", "exports/segno.svg", "construction.md"]
    checks = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
    return lambda: session.start(PROJECT, brief, outputs_, checks, budget=10.0)


def test_start_replaces_a_brief_linked_in_an_existing_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Studio(tmp_path)
    studio.plant("brief.md", "secret.txt")
    start = started(studio, tmp_path, monkeypatch)

    with pytest.raises(Stop):  # the graph is the next step: the copy went by
        start()

    assert studio.untouched()
    assert (studio.work / "brief.md").read_bytes() == BRIEF
    assert not (studio.work / "brief.md").is_symlink()
    assert studio.ledger.inputs("T-0002")["brief.md"] == hashlib.sha256(BRIEF).hexdigest()


def test_start_refuses_a_brief_swapped_for_a_link_before_it_is_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    studio = Studio(tmp_path)
    start = started(studio, tmp_path, monkeypatch)
    link_after_write(monkeypatch, runtime, "brief.md", studio.host / "secret.txt")

    with pytest.raises(OutsidePerimeter):
        start()

    assert studio.untouched()
    assert [t.id for t in studio.ledger.tickets(PROJECT)] == ["T-0001"]


# A FIFO planted where the harness reads (Task 2.F21): the open must not wait for a writer.


def returns_within(seconds: float, call: Callable[[], object], fifo: Path) -> object:
    """Runs the call in a thread and returns what it raised, or fails (instead of hanging) if it is stuck."""
    outcome: list[BaseException | None] = []

    def target() -> None:
        try:
            call()
            outcome.append(None)
        except BaseException as error:
            outcome.append(error)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        # Release the reader that waits for a writer, so a regression leaves no thread behind.
        with contextlib.suppress(OSError):
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        thread.join(1)
        pytest.fail(f"the call was still blocked after {seconds} s")
    return outcome[0]


@pytest.fixture
def fifo_tree(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "work"
    (work / "real").mkdir(parents=True)
    fifo = work / "real" / "trappola.png"
    os.mkfifo(fifo)
    return work, fifo


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


# A bound on what the harness reads whole (Tasks 2.F41, 2.F42). A sparse file stands for what the sandbox
# can write: it has the size and none of the cost.


def sparse(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


class ReadSpy:
    """Records the size asked of every `read` on the files `read_under` opens."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.sizes: list[int] = []
        real = os.fdopen

        def fdopen(descriptor: int, *args: object, **kwargs: object) -> object:
            handle = real(descriptor, *args, **kwargs)  # type: ignore[call-overload]
            spy = self

            class Spied:
                def __enter__(self) -> Spied:
                    handle.__enter__()
                    return self

                def __exit__(self, *exc: object) -> None:
                    handle.__exit__(*exc)

                def read(self, size: int = -1) -> bytes:
                    spy.sizes.append(size)
                    return handle.read(size)  # type: ignore[no-any-return]

            return Spied()

        monkeypatch.setattr(os, "fdopen", fdopen)


def test_read_under_without_a_limit_reads_the_whole_file(tree: tuple[Path, Path]) -> None:
    root, _ = tree
    assert files.read_under(root, "real.txt") == b"dentro"


def test_read_under_with_a_limit_returns_a_file_of_exactly_that_size(tree: tuple[Path, Path]) -> None:
    root, _ = tree
    (root / "limit.bin").write_bytes(b"x" * 2**20)
    assert files.read_under(root, "limit.bin", 2**20) == b"x" * 2**20


def test_read_under_with_a_limit_refuses_a_file_one_byte_over_it(tree: tuple[Path, Path]) -> None:
    root, _ = tree
    (root / "limit.bin").write_bytes(b"x" * (2**20 + 1))
    with pytest.raises(OutsidePerimeter) as refusal:
        files.read_under(root, "limit.bin", 2**20)
    assert str(refusal.value) == "limit.bin: supera il limite di 1 MiB"


def test_read_under_with_a_limit_reads_one_byte_past_it_and_no_more(
    tree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = tree
    sparse(root / "big.bin", 256 * 2**20)
    spy = ReadSpy(monkeypatch)
    with pytest.raises(OutsidePerimeter):
        files.read_under(root, "big.bin", 2**20)
    assert spy.sizes == [2**20 + 1]


def test_the_named_limits() -> None:
    assert files.MAX_TEXT_FILE_BYTES == 8 * 2**20
    assert files.MAX_IMAGE_FILE_BYTES == 64 * 2**20 == surface.MAX_IMAGE_FILE_BYTES
    assert files.MAX_DOCUMENT_BYTES == 256 * 2**20
    for name in ("MAX_TEXT_FILE_BYTES", "MAX_IMAGE_FILE_BYTES", "MAX_DOCUMENT_BYTES"):
        assert getattr(contract_files, name) == getattr(files, name)  # the tools module re-exports them


def over(limit: int) -> int:
    return limit + 1


TEXT_REFUSAL = "supera il limite di 8 MiB"
DOCUMENT_REFUSAL = "supera il limite di 256 MiB"
IMAGE_REFUSAL = "supera il limite di 64 MiB"


def test_read_file_refuses_a_text_file_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = tool_context(work)
    sparse(work / "note.txt", over(files.MAX_TEXT_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=TEXT_REFUSAL):
        surface.read_file(ctx, surface.ReadFile(path="note.txt"), "op1")


def test_read_file_reads_a_text_file_of_exactly_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = tool_context(work)
    sparse(work / "note.txt", files.MAX_TEXT_FILE_BYTES)
    assert surface.read_file(ctx, surface.ReadFile(path="note.txt"), "op1")["lines"] == 1
    (work / "piccolo.txt").write_text("uno\ndue\n", encoding="utf-8")
    assert surface.read_file(ctx, surface.ReadFile(path="piccolo.txt"), "op1")["text"] == "uno\ndue"


def drafted(work: Path) -> surface.ToolContext:
    """A context whose last draft made one page, that this instance has looked at."""
    ctx = tool_context(work)
    page = f"{presentation.folder_of(1)}/pagina-1.png"
    (work / page).parent.mkdir(parents=True)
    (work / page).write_bytes(png((20, 20, 20)))
    (work / presentation.pdf_of(1)).write_bytes(b"%PDF")
    key = f"{page}:{hashlib.sha256((work / page).read_bytes()).hexdigest()}"
    ctx.ledger.record_operation("op1", "i", "draft_presentation", json.dumps({"pagine": [page]}))
    ctx.ledger.record_operation("op2", "i", "view_image", json.dumps({"key": key}))
    return ctx


def test_present_concepts_refuses_a_draft_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = drafted(work)
    sparse(work / presentation.folder_of(1) / "testi.json", over(files.MAX_TEXT_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=TEXT_REFUSAL):
        surface.present_concepts(ctx, surface.ConfirmPresentation(), "op3")
    assert ctx.finished is None


def test_present_concepts_reads_a_small_draft(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = drafted(work)
    (work / presentation.folder_of(1) / "testi.json").write_text('{"proposals": []}', encoding="utf-8")
    assert surface.present_concepts(ctx, surface.ConfirmPresentation(), "op3") == {"proposals": []}


class ExportingSandbox(Sandbox):
    """Plays `vectorcraft-cli run`: writes an exported document of the size it is given."""

    def __init__(self, work: Path, ops: Path, size: int) -> None:
        super().__init__(work, ops=ops)
        self.size = size

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        export = Path(command[command.index("--export") + 1]).relative_to(JOB)
        sparse(self.work / export, self.size)
        return Completed(0, json.dumps({"step": "cmd", "result": {"id": 2}}), "")


def craft_folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    work, inputs, records = tmp_path / "work", tmp_path / "inputs", tmp_path / "records"
    for folder in (work, inputs, records):
        folder.mkdir()
    return work, inputs, records


INDEX = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
STEPS = [{"command": "path.create"}]


def test_craft_refuses_an_exported_document_over_the_limit(tmp_path: Path) -> None:
    work, inputs, records = craft_folders(tmp_path)
    sandbox = ExportingSandbox(work, inputs, over(files.MAX_DOCUMENT_BYTES))
    with pytest.raises(OutsidePerimeter, match=DOCUMENT_REFUSAL):
        craft.run_steps(sandbox, INDEX, "segno.vectorcraft", STEPS, "op1", records)
    assert not (work / "segno.vectorcraft").exists()
    assert not any(records.iterdir())


def test_craft_copies_an_exported_document_over_the_text_limit(tmp_path: Path) -> None:
    """A document can hold images: it has a limit of its own, far over the one for text."""
    work, inputs, records = craft_folders(tmp_path)
    sandbox = ExportingSandbox(work, inputs, over(files.MAX_TEXT_FILE_BYTES))
    result = craft.run_steps(sandbox, INDEX, "segno.vectorcraft", STEPS, "op1", records)
    assert result["ok"]
    assert (work / "segno.vectorcraft").stat().st_size == over(files.MAX_TEXT_FILE_BYTES)


@pytest.mark.parametrize(
    ("oversize", "limit", "refusal"),
    [
        ("op1.vectorcraft", files.MAX_DOCUMENT_BYTES, DOCUMENT_REFUSAL),
        ("op1.result.json", files.MAX_TEXT_FILE_BYTES, TEXT_REFUSAL),
    ],
)
def test_craft_refuses_a_stored_record_over_the_limit(
    tmp_path: Path, oversize: str, limit: int, refusal: str
) -> None:
    work, inputs, records = craft_folders(tmp_path)
    (records / "op1.vectorcraft").write_text("documento", encoding="utf-8")
    (records / "op1.result.json").write_text("[]", encoding="utf-8")
    sparse(records / oversize, over(limit))
    sandbox = ExportingSandbox(work, inputs, 0)
    with pytest.raises(OutsidePerimeter, match=refusal):
        craft.run_steps(sandbox, INDEX, "segno.vectorcraft", STEPS, "op1", records)


def test_craft_resumes_from_small_stored_records(tmp_path: Path) -> None:
    work, inputs, records = craft_folders(tmp_path)
    (records / "op1.vectorcraft").write_text("documento", encoding="utf-8")
    (records / "op1.result.json").write_text('[{"id": 2}]', encoding="utf-8")
    result = craft.run_steps(
        ExportingSandbox(work, inputs, 0), INDEX, "segno.vectorcraft", STEPS, "op1", records
    )
    assert result == {"ok": True, "document": "segno.vectorcraft", "results": [{"id": 2}]}
    assert (work / "segno.vectorcraft").read_text(encoding="utf-8") == "documento"


def test_render_refuses_an_image_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    sparse(work / "grande.png", over(files.MAX_IMAGE_FILE_BYTES))
    ledger = Ledger(tmp_path / "l.sqlite")
    with pytest.raises(OutsidePerimeter, match=IMAGE_REFUSAL):
        render.render_one(Sandbox(work), ledger, "p", "grande.png")


def test_the_board_refuses_a_sketch_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    sketch = sparse(work / "explorations/r1/a/schizzo-a.png", over(files.MAX_IMAGE_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=IMAGE_REFUSAL):
        board.build([("V", sketch)], work / "board/r1/tavola.png")
    assert not (work / "board").exists()


def test_the_presentation_refuses_a_mark_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    mark = sparse(work / "proposals/r1/v/proposta-v.png", over(files.MAX_IMAGE_FILE_BYTES))
    item = presentation.Proposal("V", "Il merlo", "L'idea", "Perché", "Il limite", mark, ())
    with pytest.raises(OutsidePerimeter, match=IMAGE_REFUSAL):
        presentation.build([item], "V", "Regge meglio", work / "presentation/r1")
    assert not list((work / "presentation/r1").glob("*.pdf"))


def test_a_refused_open_leaks_no_descriptor(fifo_tree: tuple[Path, Path]) -> None:
    work, fifo = fifo_tree
    before = len(os.listdir("/proc/self/fd"))
    for _ in range(5):
        error = returns_within(5, lambda: files.read_under(work, "real/trappola.png"), fifo)
        assert isinstance(error, OutsidePerimeter)
    assert len(os.listdir("/proc/self/fd")) == before


# The graph nodes read what the sandbox wrote under a limit of its own kind (Task 2.F41, 2.F42, same pattern).


def test_the_board_node_refuses_a_brief_over_the_limit(tmp_path: Path) -> None:
    studio = board_studio(tmp_path)
    sparse(studio.work / "brief.md", over(files.MAX_TEXT_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=TEXT_REFUSAL):
        studio.node("make_board")(studio.state())


def test_the_select_node_refuses_a_sheet_over_the_limit(tmp_path: Path) -> None:
    studio = select_studio(tmp_path)
    sparse(studio.work / at("foglio-a.png"), over(files.MAX_IMAGE_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=IMAGE_REFUSAL):
        studio.node("select")(studio.state())
    assert not (studio.work / "board/r1/fogli/Z.png").exists()


@pytest.mark.parametrize(
    ("planted", "limit", "refusal"),
    [
        ("explorations/r1/applicazioni.json", files.MAX_TEXT_FILE_BYTES, TEXT_REFUSAL),
        ("brief.md", files.MAX_TEXT_FILE_BYTES, TEXT_REFUSAL),
        (at("scheda.json"), files.MAX_TEXT_FILE_BYTES, TEXT_REFUSAL),
        (at("schizzo-a.png"), files.MAX_IMAGE_FILE_BYTES, IMAGE_REFUSAL),
    ],
)
def test_the_proposals_node_refuses_a_file_over_the_limit(
    tmp_path: Path, planted: str, limit: int, refusal: str
) -> None:
    studio = proposals_studio(tmp_path)
    sparse(studio.work / planted, over(limit))
    with pytest.raises(OutsidePerimeter, match=refusal):
        studio.node("prepare_proposals")(studio.state())
    assert studio.ledger.children(studio.root) == []


def test_the_production_node_refuses_a_master_over_the_limit(tmp_path: Path) -> None:
    studio = production_studio(tmp_path)
    sparse(studio.work / "proposals/r1/z/proposta-z.vectorcraft", over(files.MAX_DOCUMENT_BYTES))
    with pytest.raises(OutsidePerimeter, match=DOCUMENT_REFUSAL):
        studio.node("start_production")(studio.state())
    assert studio.ledger.children(studio.root) == []


def test_the_production_node_copies_a_master_over_the_text_limit(tmp_path: Path) -> None:
    studio = production_studio(tmp_path)
    sparse(studio.work / "proposals/r1/z/proposta-z.vectorcraft", over(files.MAX_TEXT_FILE_BYTES))
    studio.node("start_production")(studio.state())
    assert (studio.work / TARGET).stat().st_size == over(files.MAX_TEXT_FILE_BYTES)
