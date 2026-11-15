"""The read slice reads the transcripts: from each, only the tools used and their refusals."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from agency.agents.transcript import Transcript
from agency.contracts.layout import DataLayout
from agency.contracts.outcome import Outcome, OutcomeState
from agency.contracts.project import ProjectName
from agency.insights.adapters.transcripts import JsonlTranscripts
from support.insights import answer, results, turn, use


def test_transcripts_give_every_tool_call_and_the_refusals_with_their_words(tmp_path: Path) -> None:
    """The engine writes the transcript and insights reads it through the same path: DataLayout."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append({"role": "user", "content": "Il brief del cliente"})
    transcript.append(
        turn({"type": "text", "text": "Guardo il file"}, use("u1", "view_image"), use("u2", "deliver"))
    )
    content = [{"type": "text", "text": "consegna rifiutata:"}, {"type": "text", "text": "manca la prova"}]
    transcript.append(
        results(
            answer("u1", "ok"),
            {"type": "tool_result", "tool_use_id": "u2", "is_error": True, "content": content},
        )
    )
    transcript.append(turn(use("u3", "deliver")))
    transcript.append(results(answer("u3", '{"ok": true}')))

    reading = JsonlTranscripts(layout).read()

    assert [(item.project, item.instance, item.turn, item.tool, item.refusal) for item in reading.calls] == [
        ("merlo4", "T-0002-a1", 1, "view_image", None),
        ("merlo4", "T-0002-a1", 1, "deliver", "consegna rifiutata:\nmanca la prova"),
        ("merlo4", "T-0002-a1", 2, "deliver", None),
    ]
    assert [item.seq for item in reading.calls] == [1, 2, 3]
    assert reading.unreadable == 0


def test_a_half_written_line_is_counted_and_skipped_and_the_stamp_names_each_transcript(
    tmp_path: Path,
) -> None:
    layout = DataLayout(tmp_path)
    Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1")).append(turn(use("u1", "render")))
    with layout.transcript(ProjectName("merlo4"), "T-0002-a1").open("a", encoding="utf-8") as handle:
        handle.write('{"message": {"role": "user", "cont')  # the engine is writing

    transcripts = JsonlTranscripts(layout)

    reading = transcripts.read()
    assert ([item.tool for item in reading.calls], reading.unreadable) == (["render"], 1)
    assert [item.name for item in transcripts.stamp()] == ["runs/merlo4/T-0002-a1.jsonl"]


def test_a_line_torn_inside_a_utf8_character_counts_as_unreadable(tmp_path: Path) -> None:
    """The engine writes Italian unescaped, so a line can stop after the first byte of `è`."""
    layout = DataLayout(tmp_path)
    path = layout.transcript(ProjectName("merlo4"), "T-0002-a1")
    Transcript(path).append(turn(use("u1", "render")))
    with path.open("ab") as handle:
        handle.write(b'{"a":"\xc3')  # the engine was writing "è"
    transcripts = JsonlTranscripts(layout)

    reading = transcripts.read()
    assert reading.unreadable == 1
    assert [call.tool for call in reading.calls] == ["render"]
    record = transcripts.transcript("merlo4", "T-0002-a1")
    assert record is not None
    assert record.unreadable == 1
    assert [tool.name for item in record.turns for tool in item.tools] == ["render"]
    assert len(Transcript(path).messages()) == 1  # the engine reads bytes, and repairs this same file


def test_a_long_refusal_keeps_its_head_and_its_tail_and_says_where_it_was_cut(tmp_path: Path) -> None:
    """craft_run answers with the log of its steps: the error can be at the end."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append(turn(use("u1", "craft_run")))
    log = "passo 1 ok\n" + "x" * 5000 + "\nstep 9 (select.set): no such object"
    transcript.append(results(answer("u1", log, error=True)))
    (call,) = JsonlTranscripts(layout).read().calls
    assert call.refusal is not None and len(call.refusal) == 2000
    assert call.refusal.startswith("passo 1 ok") and call.refusal.endswith("no such object")
    assert "\n[…]\n" in call.refusal


PIXEL = base64.b64encode(b"\x89PNG\r\n\x1a\n un pixel").decode()


def image_block(media_type: str = "image/png", data: str = PIXEL) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def replayed(tmp_path: Path) -> DataLayout:
    """An instance as the engine writes it: the task, two turns, a reminder, the outcome."""
    layout = DataLayout(tmp_path)
    transcript = Transcript(layout.transcript(ProjectName("merlo4"), "T-0002-a1"))
    transcript.append({"role": "user", "content": "TICKET T-0002: il segno"})
    transcript.append(
        turn(
            {"type": "thinking", "thinking": "Prima guardo il render", "signature": "firma"},
            {"type": "redacted_thinking", "data": "illeggibile"},
            {"type": "text", "text": "Guardo il file"},
            {"type": "tool_use", "id": "u1", "name": "view_image", "input": {"path": "segno.png"}},
            {"type": "tool_use", "id": "u2", "name": "deliver", "input": {}},
        ),
        request_id="req_1",
    )
    shown = {
        "type": "tool_result",
        "tool_use_id": "u1",
        "content": [{"type": "text", "text": "il render"}, image_block()],
    }
    transcript.append(results(shown, answer("u2", "consegna rifiutata", error=True)))
    transcript.append({"role": "user", "content": "Ricorda di consegnare"})
    transcript.append(turn(use("u3", "view_image")), request_id="req_2")
    transcript.append(
        results({"type": "tool_result", "tool_use_id": "u3", "content": [image_block("image/svg+xml")]})
    )
    transcript.finish(Outcome(state=OutcomeState.DELIVERED, note="fatto"))
    return layout


def test_a_transcript_reads_as_the_task_then_turn_after_turn(tmp_path: Path) -> None:
    record = JsonlTranscripts(replayed(tmp_path)).transcript("merlo4", "T-0002-a1")
    assert record is not None
    assert (record.task, record.outcome_state, record.outcome_note, record.unreadable) == (
        "TICKET T-0002: il segno",
        "delivered",
        "fatto",
        0,
    )
    first, second = record.turns
    assert (first.request_id, first.thinking, first.hidden_thinking, first.text) == (
        "req_1",
        ["Prima guardo il render"],
        1,
        ["Guardo il file"],
    )
    assert [(tool.name, tool.answered, tool.refused, tool.result) for tool in first.tools] == [
        ("view_image", True, False, "il render"),
        ("deliver", True, True, "consegna rifiutata"),
    ]
    assert json.loads(first.tools[0].input) == {"path": "segno.png"}
    assert [(image.index, image.media_type, image.servable) for image in first.tools[0].images] == [
        (0, "image/png", True)
    ]
    assert (first.notes, second.request_id) == (["Ricorda di consegnare"], "req_2")
    # An image of a type the dashboard does not serve is counted, but not offered.
    assert [(image.index, image.media_type, image.servable) for image in second.tools[0].images] == [
        (1, "image/svg+xml", False)
    ]
    assert record.images == 2


def test_an_image_comes_out_of_its_transcript_only_if_it_is_a_picture(tmp_path: Path) -> None:
    transcripts = JsonlTranscripts(replayed(tmp_path))
    picture = transcripts.image("merlo4", "T-0002-a1", 0)
    assert picture is not None and (picture.media_type, picture.data) == (
        "image/png",
        base64.b64decode(PIXEL),
    )
    assert transcripts.image("merlo4", "T-0002-a1", 1) is None  # SVG: it could hold scripts
    assert transcripts.image("merlo4", "T-0002-a1", 2) is None


def test_a_name_that_is_not_an_instance_never_becomes_a_path(tmp_path: Path) -> None:
    """Two defences, each with its own case: the name must be an instance's, and the file must be in the
    transcripts folder."""
    transcripts = JsonlTranscripts(replayed(tmp_path))
    line = '{"message": {"role": "user", "content": "x"}}\n'
    (tmp_path / "segreto.jsonl").write_text(line, encoding="utf-8")
    (tmp_path / "runs" / "merlo4" / "appunti.jsonl").write_text(
        line, encoding="utf-8"
    )  # inside, not an instance
    (tmp_path / "fuori").mkdir()
    (tmp_path / "fuori" / "T-0002-a1.jsonl").write_text(line, encoding="utf-8")  # an instance, but outside
    assert transcripts.transcript("merlo4", "appunti") is None
    assert transcripts.transcript("../fuori", "T-0002-a1") is None
    assert transcripts.image("../fuori", "T-0002-a1", 0) is None
    nested = tmp_path / "runs" / "acme" / "v2"  # inside the folder, but not a project name (COR-013)
    nested.mkdir(parents=True)
    (nested / "T-0002-a1.jsonl").write_text(line, encoding="utf-8")
    assert transcripts.transcript("acme/v2", "T-0002-a1") is None
    assert transcripts.image("acme/v2", "T-0002-a1", 0) is None
    for project, instance in [
        ("..", "segreto"),
        ("merlo4", "../../segreto"),
        ("merlo4", "T-0099-a1"),
        ("../merlo4", "T-0002-a1"),
    ]:
        assert transcripts.transcript(project, instance) is None, (project, instance)
        assert transcripts.image(project, instance, 0) is None


def test_missing_transcripts_are_not_an_error(tmp_path: Path) -> None:
    transcripts = JsonlTranscripts(DataLayout(tmp_path))
    assert (transcripts.read().calls, transcripts.read().unreadable, transcripts.stamp()) == ([], 0, [])
