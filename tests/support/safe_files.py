"""What more than one safe-files test file uses: the planted links, the studio and the readers' refusals."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from PIL import Image

from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.concept import ConceptCard
from agency.contracts.ledger import ConceptEntry
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import parse_project_name
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.process import graph as workflow
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.files import OutsidePerimeter
from agency.workshop.sandbox import Sandbox
from support.rules import RULES

# The readers that open work files (Task 2.2). The host folder holds the sentinel: a red image and an SVG
# that only the host has. The sandbox leaves a link to it where a reader looks.

RED = (200, 0, 0)


def png(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


def shows_red(data: bytes) -> bool:
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
    return RED in {color for _, color in rgb.getcolors(rgb.width * rgb.height) or []}


def tool_context(work: Path) -> ToolContext:
    ledger, store = Ledger(work.parent / "l.sqlite"), FileStore(work.parent / "artifacts")
    return ToolContext("critic", "p", "T-1", "i", ledger, Sandbox(work), CommandIndex([]), store, rules=RULES)


def outputs(work: Path) -> list[Path]:
    """The regular files under the work folder, without going through a link."""
    return [path for path in work.rglob("*") if path.is_file() and not path.is_symlink()]


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
        self.graph = workflow.build(runner, self.ledger, self.settings, InMemorySaver(), rules=RULES)
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
        row = ConceptEntry(
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


def at(name: str) -> str:
    return f"explorations/r1/{LETTER}/{name}"


# make_board (2.F3)


def board_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept(delivered=True)
    studio.explorers_work()
    return studio


# select (2.F4)


def select_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.explorers_work()
    studio.put("board/r1/tavola.png", png((50, 50, 50)))
    return studio


# prepare_proposals (2.F5)


def proposals_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.explorers_work()
    return studio


# start_production (2.F7)


def production_studio(tmp_path: Path) -> Studio:
    studio = Studio(tmp_path)
    studio.concept()
    studio.proposer_work()
    return studio


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
