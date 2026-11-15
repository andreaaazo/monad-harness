"""What the harness reads whole has a bound: a sparse file stands for what the sandbox can write."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from agency.contracts import files as contract_files
from agency.ledger import Ledger
from agency.studio.presentation import document
from agency.studio.presentation.tools import (
    ConfirmPresentation,
    present_concepts,
)
from agency.toolkit import files as file_tools
from agency.toolkit.base import ToolContext
from agency.workshop import board, craft, files, render
from agency.workshop.craft import Command, CommandIndex
from agency.workshop.files import OutsidePerimeter
from agency.workshop.sandbox import JOB, Completed, Sandbox
from support.safe_files import (
    TARGET,
    at,
    board_studio,
    png,
    production_studio,
    proposals_studio,
    returns_within,
    select_studio,
    tool_context,
)

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
    assert files.MAX_IMAGE_FILE_BYTES == 64 * 2**20 == file_tools.MAX_IMAGE_FILE_BYTES
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
        file_tools.read_file(ctx, file_tools.ReadFile(path="note.txt"), "op1")


def test_read_file_reads_a_text_file_of_exactly_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = tool_context(work)
    sparse(work / "note.txt", files.MAX_TEXT_FILE_BYTES)
    assert file_tools.read_file(ctx, file_tools.ReadFile(path="note.txt"), "op1")["lines"] == 1
    (work / "piccolo.txt").write_text("uno\ndue\n", encoding="utf-8")
    assert file_tools.read_file(ctx, file_tools.ReadFile(path="piccolo.txt"), "op1")["text"] == "uno\ndue"


def drafted(work: Path) -> ToolContext:
    """A context whose last draft made one page, that this instance has looked at."""
    ctx = tool_context(work)
    page = f"{document.folder_of(1)}/pagina-1.png"
    (work / page).parent.mkdir(parents=True)
    (work / page).write_bytes(png((20, 20, 20)))
    (work / document.pdf_of(1)).write_bytes(b"%PDF")
    key = f"{page}:{hashlib.sha256((work / page).read_bytes()).hexdigest()}"
    ctx.ledger.record_operation("op1", "i", "draft_presentation", json.dumps({"pagine": [page]}))
    ctx.ledger.record_operation("op2", "i", "view_image", json.dumps({"key": key}))
    return ctx


def test_present_concepts_refuses_a_draft_over_the_limit(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = drafted(work)
    sparse(work / document.folder_of(1) / "testi.json", over(files.MAX_TEXT_FILE_BYTES))
    with pytest.raises(OutsidePerimeter, match=TEXT_REFUSAL):
        present_concepts(ctx, ConfirmPresentation(), "op3")
    assert ctx.finished is None


def test_present_concepts_reads_a_small_draft(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    ctx = drafted(work)
    (work / document.folder_of(1) / "testi.json").write_text('{"proposals": []}', encoding="utf-8")
    assert present_concepts(ctx, ConfirmPresentation(), "op3") == {"proposals": []}


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
    item = document.Proposal("V", "Il merlo", "L'idea", "Perché", "Il limite", mark, ())
    with pytest.raises(OutsidePerimeter, match=IMAGE_REFUSAL):
        document.build([item], "V", "Regge meglio", work / "presentation/r1")
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


@pytest.fixture
def layout(tmp_path: Path) -> Path:
    """projects/merlo/work/exports with a file, an operator's alias to the project and a link to it from
    elsewhere, and a host folder outside."""
    (tmp_path / "projects/merlo/work/exports").mkdir(parents=True)
    (tmp_path / "projects/merlo/work/exports/a.svg").write_text("<svg/>")
    (tmp_path / "host").mkdir()
    (tmp_path / "home/sub/inner").mkdir(parents=True)
    (tmp_path / "home/m").symlink_to(tmp_path / "projects/merlo", target_is_directory=True)
    (tmp_path / "home/op").symlink_to(tmp_path / "home/sub/inner", target_is_directory=True)
    (tmp_path / "home/rel").symlink_to(
        "sub/inner", target_is_directory=True
    )  # read from home/, as the kernel does
    (tmp_path / "projectsx").mkdir()  # a sibling whose name starts with the folder's
    return tmp_path


@pytest.mark.parametrize(
    ("typed", "parts"),
    [
        ("projects/merlo/work/exports/a.svg", ("merlo", "work", "exports", "a.svg")),
        ("home/../projects/merlo/work/exports/a.svg", ("merlo", "work", "exports", "a.svg")),
        ("home/m/work/exports/a.svg", ("merlo", "work", "exports", "a.svg")),  # the operator's alias
        ("home/op/../../../projects/merlo/work/a.svg", ("merlo", "work", "a.svg")),  # `..` after a link
        (
            "projects/merlo/work/exports/../nuova/b.svg",
            ("merlo", "work", "nuova", "b.svg"),
        ),  # real folders only
        ("projects/merlo/work/nuova/cartella/b.svg", ("merlo", "work", "nuova", "cartella", "b.svg")),
        ("projects", ()),
    ],
)
def test_land_finds_the_projects_folder_as_the_kernel_does(
    layout: Path, typed: str, parts: tuple[str, ...]
) -> None:
    landing = contract_files.land(layout / typed, layout / "projects")
    assert landing.parts == parts
    assert landing.real == (layout / "projects").joinpath(*parts)


def test_land_reads_a_leading_double_slash_as_one(layout: Path) -> None:
    landing = contract_files.land(Path(f"/{layout}/projects/merlo"), layout / "projects")
    assert landing.parts == ("merlo",)


@pytest.mark.parametrize(
    ("typed", "real"),
    [
        ("home/op/../x.svg", "home/sub/x.svg"),
        ("home/rel/x.svg", "home/sub/inner/x.svg"),  # a relative target
        ("projectsx/a.svg", "projectsx/a.svg"),  # beside the projects folder, not below it
    ],
)
def test_land_follows_the_operators_links_outside_the_projects_folder(
    layout: Path, typed: str, real: str
) -> None:
    landing = contract_files.land(layout / typed, layout / "projects")
    assert (landing.parts, landing.real) == (None, layout / real)


@pytest.mark.parametrize(
    "typed", ["projects/merlo/work/exports/a.svg/../b.svg", "projects/merlo/work/exports/a.svg/x/../b.svg"]
)
def test_land_refuses_dotdot_after_a_file(layout: Path, typed: str) -> None:
    # The kernel answers ENOTDIR: a file is no folder to climb from.
    with pytest.raises(contract_files.OutsidePerimeter):
        contract_files.land(layout / typed, layout / "projects")


@pytest.mark.parametrize(
    "typed",
    [
        "projects/merlo/work/link/x.svg",  # the planted link itself
        "home/m/work/link/x.svg",  # through the operator's alias
        "home/op/../../../projects/merlo/work/link/x.svg",  # through `..` after the operator's link
        "projects/merlo/work/link/../exports/a.svg",  # a link then `..`: the kernel climbs from its target
        "projects/merlo/work/near/a.svg",  # a relative link that stays below the projects folder
    ],
)
def test_land_refuses_a_link_below_the_projects_folder_whatever_the_spelling(
    layout: Path, typed: str
) -> None:
    (layout / "projects/merlo/work/link").symlink_to(layout / "host", target_is_directory=True)
    (layout / "projects/merlo/work/near").symlink_to("exports", target_is_directory=True)
    with pytest.raises(contract_files.OutsidePerimeter, match="fuori dalla cartella del lavoro"):
        contract_files.land(layout / typed, layout / "projects")


def test_land_refuses_dotdot_after_a_folder_that_does_not_exist(layout: Path) -> None:
    with pytest.raises(contract_files.OutsidePerimeter):
        contract_files.land(layout / "projects/merlo/nuova/../../../host/x.svg", layout / "projects")


def test_land_refuses_a_loop_of_links(layout: Path) -> None:
    (layout / "home/a").symlink_to(layout / "home/b")
    (layout / "home/b").symlink_to(layout / "home/a")
    with pytest.raises(contract_files.OutsidePerimeter):
        contract_files.land(layout / "home/a/x.svg", layout / "projects")


def test_unlink_under_refuses_a_folder_swapped_for_a_link(layout: Path) -> None:
    (layout / "host/a.svg").write_text("del proprietario")
    (layout / "projects/merlo/work/fuori").symlink_to(layout / "host", target_is_directory=True)
    with pytest.raises(contract_files.OutsidePerimeter):
        contract_files.unlink_under(layout / "projects", "merlo/work/fuori/a.svg")
    assert (layout / "host/a.svg").read_text() == "del proprietario"
