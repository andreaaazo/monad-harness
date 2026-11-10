"""The no-follow helpers for the files the harness opens under the work folder (SEC-001, Task 2.1)."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
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
from agency.tools import board, files, presentation, render, surface
from agency.tools.craft import CommandIndex
from agency.tools.files import OutsidePerimeter
from agency.tools.sandbox import Sandbox
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
