"""Which tools each role gets, and where they stop it: the toolbox with recorded answers and real Craft."""

from __future__ import annotations

import io
import json
import tracemalloc
from pathlib import Path

import pytest
from PIL import Image

from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.contracts.ticket import Status
from agency.entrypoints import cli
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop import master
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import (
    Sandbox,
)
from support.flow import needs_craft, production_spec, runner, steps, use
from support.rules import RULES
from support.scripted import turn
from support.settings import settings


@needs_craft
def test_author_cannot_deliver_without_master_then_can(tmp_path: Path) -> None:
    config = settings(tmp_path)
    responses = [
        turn(use("deliver", "t1", note="fatto", verdict=None)),
        turn(use("craft_run", "t2", document="source/segno.vectorcraft", steps=steps())),
        turn(use("export_master", "t3", master="source/segno.vectorcraft", output="exports/segno.svg")),
        turn(
            use("run_check", "t4", check="master_open", file="source/segno.vectorcraft"),
            use("run_check", "t5", check="svg_audit", file="exports/segno.svg"),
        ),
        turn(use("deliver", "t6", note="master e svg", verdict=None)),
    ]
    run, transport, ledger = runner(config, responses)
    ticket = ledger.open(production_spec(), "p")
    outcome = run.run(ticket)
    assert outcome.state == "delivered"
    assert ledger.status(ticket)[0] is Status.DELIVERED
    refused = transport.requests[1]["messages"][-1]["content"][0]
    assert refused["is_error"] and "consegna rifiutata" in refused["content"]
    assert {r.signer for r in ledger.evidence("p")} == {"identity-designer"}


def test_schemas_have_no_identity_field(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    context = ToolContext(
        "identity-designer",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    text = json.dumps(Toolbox(context).definitions())
    for field in ('"by"', '"actor"', '"signer"', '"from"', '"sender"'):
        assert field not in text


def test_role_cannot_use_tools_outside_its_set(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    ticket = ledger.open(production_spec(), "p")
    context = ToolContext(
        "critic",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    result = Toolbox(context).call("x", "craft_run", {"document": "a.vectorcraft", "steps": []})
    assert result["is_error"]


def test_reviewer_writes_only_reports(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    box = Toolbox(context)
    assert box.call("a", "write_file", {"path": "source/note.md", "content": "x"})["is_error"]
    assert not box.call("b", "write_file", {"path": "reviews/r.md", "content": "x"}).get("is_error")


def test_author_cannot_write_vectors_by_hand(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    context = ToolContext(
        "identity-designer",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    result = Toolbox(context).call("a", "write_file", {"path": "exports/a.svg", "content": "<svg/>"})
    assert result["is_error"]


def test_path_outside_the_job_is_refused(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    assert Toolbox(context).call("a", "read_file", {"path": "../../etc/passwd"})["is_error"]


def test_child_ticket_outside_org_is_refused(tmp_path: Path) -> None:
    config = settings(tmp_path)
    ledger = Ledger(config.layout.ledger)
    context = ToolContext(
        "design-director",
        "p",
        "T-1",
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    arguments = {
        "title": "Ricerca",
        "request": "r",
        "type": "ricerca",
        "assignee": "researcher",
        "outputs": ["a.md"],
        "checks": {},
    }
    assert "non può aprire" in Toolbox(context).call("a", "open_ticket", arguments)["content"]


def test_master_problem_reads_only_the_header(tmp_path: Path) -> None:
    with (tmp_path / "x.blend").open("wb") as handle:
        handle.write(b"BLENDER")
        handle.truncate(64 * 2**20)  # sparse: no disk, and a full read would show as 64 MiB of memory
    tracemalloc.start()
    try:
        why = master.problem(Sandbox(tmp_path), "x.blend")
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert why is None
    assert peak < 2**20


def test_view_image_refuses_a_huge_file(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "PNG")
    # A valid image, which view_image would otherwise show: zeros alone would be refused as unreadable. Its
    # sparse tail makes it twice the limit, so the peak shows that the read stops near the limit.
    with (tmp_path / "big.png").open("wb") as handle:
        handle.write(buffer.getvalue())
        handle.truncate(2 * 64 * 2**20)
    context = ToolContext(
        "critic",
        "p",
        "T-1",
        "i",
        Ledger(tmp_path / "ledger.db"),
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    tracemalloc.start()
    try:
        result = Toolbox(context).call("a", "view_image", {"path": "big.png"})
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result.get("is_error")
    assert "64 MiB" in result["content"]
    assert peak < 96 * 2**20


def test_cli_lists_new_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(["--help"])
    assert stop.value.code == 0
    printed = capsys.readouterr().out
    for command in ("run", "resume", "decide", "report"):
        assert command in printed
