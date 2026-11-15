"""The no-follow helpers in the graph nodes: a link the sandbox leaves where a node reads or writes is refused
or replaced."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest

from agency.studio import shared
from agency.studio.presentation import document
from agency.workshop.files import OutsidePerimeter
from support.safe_files import (
    BRIEF,
    MASTER,
    TARGET,
    Plant,
    Studio,
    at,
    board_studio,
    leaks,
    link_after_write,
    png,
    production_studio,
    proposals_studio,
    refused,
    select_studio,
)


def overwrites(studio: Studio, run: Callable[[], object], planted: Plant) -> None:
    """The planted file link is replaced by the harness's own file; nothing reaches the host."""
    studio.plant(*planted)
    run()
    assert studio.untouched()
    assert not (studio.work / planted[0]).is_symlink()
    assert not leaks(studio.work)


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
    link_after_write(monkeypatch, shared, "schizzo.png", studio.host / "secret.png")

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

    document.sheet(mark_of(studio), (), output)

    assert output.is_file()


@pytest.mark.parametrize("planted", [("proposals/r1", ""), ("proposals/r1", "absent")])
def test_the_sheet_refuses_a_linked_folder(tmp_path: Path, planted: Plant) -> None:
    studio = Studio(tmp_path)
    mark = mark_of(studio)
    refused(studio, lambda: document.sheet(mark, (), studio.work / "proposals/r1/insieme-z.png"), planted)


def test_the_sheet_replaces_a_linked_file(tmp_path: Path) -> None:
    studio = Studio(tmp_path)
    mark = mark_of(studio)
    overwrites(
        studio,
        lambda: document.sheet(mark, (), studio.work / "proposals/r1/insieme-z.png"),
        ("proposals/r1/insieme-z.png", "secret.png"),
    )


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
