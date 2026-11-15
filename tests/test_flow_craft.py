"""The Craft and file tools with real VectorCraft: compute, craft_run and their resume records."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from agency.agents.loop import AgentRunner
from agency.agents.toolbox import Toolbox
from agency.artifacts import FileStore
from agency.contracts import phase
from agency.contracts.project import ProjectName
from agency.gateway import ModelGateway
from agency.ledger import Ledger
from agency.toolkit.base import ToolContext
from agency.workshop import craft
from agency.workshop.craft import Command, CommandIndex
from agency.workshop.sandbox import (
    JOB,
    Completed,
    Sandbox,
)
from support.flow import bare_context, production_spec, steps, use
from support.rules import RULES
from support.scripted import ScriptedTransport, turn
from support.settings import settings


@pytest.mark.sandbox
def test_compute_runs_the_script_and_returns_exit_and_output(tmp_path: Path) -> None:
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    result = box.call("c1", "compute", {"code": "print(6 * 7)"})
    assert json.loads(result["content"]) == {"exit": 0, "output": "42\n"}


class CountingSandbox(Sandbox):
    """Plays `vectorcraft-cli run`: writes the exported document and prints one result per command."""

    def __init__(self, work: Path, ops: Path) -> None:
        super().__init__(work, ops=ops)
        self.calls: list[list[str]] = []

    def run(self, command: list[str], timeout: float = 120) -> Completed:
        self.calls.append(command)
        export = Path(command[command.index("--export") + 1]).relative_to(JOB)
        (self.work / export).write_text("documento costruito", encoding="utf-8")
        lines = [json.dumps({"step": "cmd", "result": {"id": 2}}), json.dumps({"step": "open"}), "non json"]
        return Completed(0, "\n".join(lines), "")


def harness_folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The work folder, and the harness folders outside it: inputs bound at /ops, and records (ADR-0044)."""
    layout = settings(tmp_path).layout
    work = tmp_path / "work"
    work.mkdir()
    inputs = layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True)
    return work, inputs, layout.ops_records(ProjectName("p"), "i")


def test_craft_run_replays_its_stored_result_on_resume(tmp_path: Path) -> None:
    """The steps run once. A second call with the same operation id copies the built document again."""
    work, inputs, records = harness_folders(tmp_path)
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"
    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    (work / master).unlink()  # the copy the crash, or a later edit, took away

    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"


@pytest.mark.sandbox
def test_compute_script_lives_outside_the_work_folder(tmp_path: Path) -> None:
    """The agent's compute script lives in /ops, bound read-only, and /job has no `.ops` (SEC-001, ADR-0044).

    The sandboxed code can neither rewrite its own script nor leave a file in /ops for the harness to find.
    """
    config = settings(tmp_path)
    probe = (
        "import errno, os, sys\n"
        "print(sys.argv[0])\n"
        "print(os.path.exists('/job/.ops'))\n"
        "for path in (sys.argv[0], '/ops/x'):\n"
        "    try:\n"
        "        open(path, 'a').close()\n"
        "        print('written')\n"
        "    except OSError as error:\n"
        "        print(errno.errorcode[error.errno])\n"
    )
    ledger = Ledger(config.layout.ledger)
    ledger.set_project("p", 25.0)
    transport = ScriptedTransport(
        [turn(use("compute", "c1", code=probe)), turn(use("block", "c2", reason="prova finita"))]
    )
    gateway = ModelGateway(transport, ledger, config)
    run = AgentRunner(
        gateway, ledger, config, CommandIndex([]), FileStore(config.layout.artifacts), rules=RULES
    )
    ticket = ledger.open(production_spec(), "p")

    run.run(ticket)

    result = json.loads(transport.requests[1]["messages"][-1]["content"][0]["content"])
    script, *seen = result["output"].split()
    assert seen == ["False", "EROFS", "EROFS"]
    assert PurePosixPath(script).parent == PurePosixPath("/ops")
    inputs = config.layout.ops_inputs(ProjectName("p"), phase.instance(ticket, 1))
    assert (inputs / PurePosixPath(script).name).read_text(encoding="utf-8") == probe
    assert not (inputs / "x").exists()
    assert not (config.project_dir(ProjectName("p")) / "work" / ".ops").exists()


def test_craft_run_resume_reads_only_the_harness_record(tmp_path: Path) -> None:
    """Whatever sandboxed code writes into /job is never read on resume: not at the old `.ops` place, not over
    the partial export. The record is the harness's copy, outside any sandbox (SEC-001, ADR-0044)."""
    work, inputs, records = harness_folders(tmp_path)
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"
    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    for forged in (".ops/op1.result.json", ".ops/op1.vectorcraft", ".partial/op1.vectorcraft"):
        (work / forged).parent.mkdir(exist_ok=True)
        (work / forged).write_text('["falso"]', encoding="utf-8")
    (work / master).unlink()

    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"
    # The plan is a harness input too: the sandbox reads it from /ops, never from /job.
    command = sandbox.calls[0]
    assert command[command.index("--commands") + 1] == "/ops/op1.steps.json"
    assert json.loads((inputs / "op1.steps.json").read_text(encoding="utf-8")) == steps()[:1]


def test_resume_with_a_record_only_in_the_old_place_reruns_once(tmp_path: Path) -> None:
    """A project paused in a craft_run before ADR-0044 kept its record in /job/.ops. On resume the steps run
    once more, and that leftover is never read as a record (Review focus 3)."""
    work, inputs, records = harness_folders(tmp_path)
    (work / ".ops").mkdir()
    (work / ".ops/op1.result.json").write_text('[{"id": 1}]', encoding="utf-8")
    (work / ".ops/op1.vectorcraft").write_text("documento vecchio", encoding="utf-8")
    sandbox = CountingSandbox(work, inputs)
    index = CommandIndex([Command("path.create", "Crea un tracciato", "Tracciato", "d")])
    master = "source/segno.vectorcraft"

    first = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)
    second = craft.run_steps(sandbox, index, master, steps()[:1], "op1", records)

    assert len(sandbox.calls) == 1
    assert first == second == {"ok": True, "document": master, "results": [{"id": 2}]}
    assert (work / master).read_text(encoding="utf-8") == "documento costruito"


def test_list_files_hides_the_partial_exports(tmp_path: Path) -> None:
    """craft_run's partial exports are the harness's, like the old `.ops`: list_files does not show them."""
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    (tmp_path / ".partial").mkdir()
    (tmp_path / ".partial/op1.vectorcraft").write_text("parziale", encoding="utf-8")
    (tmp_path / "nota.md").write_text("nota", encoding="utf-8")

    listed = json.loads(box.call("l1", "list_files", {})["content"])["files"]

    assert "nota.md" in listed
    assert ".partial/op1.vectorcraft" not in listed


def test_big_images_are_reduced_and_rereads_are_allowed(tmp_path: Path) -> None:
    from PIL import Image

    config = settings(tmp_path)
    Image.new("RGB", (3000, 400)).save(tmp_path / "big.png")
    Image.new("RGB", (400, 400)).save(tmp_path / "ok.png")
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
    reduced = box.call("a", "view_image", {"path": "big.png"})
    assert not reduced.get("is_error") and "ridotta" in str(reduced["content"])
    assert not box.call("b", "view_image", {"path": "ok.png"}).get("is_error")
    assert not box.call("c", "view_image", {"path": "ok.png"}).get("is_error")
    again = box.call("d", "view_image", {"path": "ok.png"})
    assert not again.get("is_error") and "già guardata" in str(again["content"])
