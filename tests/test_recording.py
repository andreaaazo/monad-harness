"""Live runs are recorded keyed by request and replayed in tests: nothing here calls the API (ADR-0048)."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
import httpx2
import pytest

from agency import cli
from agency.config import Settings
from agency.contracts.project import ProjectName
from agency.gateway import AnthropicTransport, RecordingTransport, request_key
from agency.ledger import Ledger
from agency.ledger.models import TicketRow
from agency.runtime import Session, open_session
from support.replay import MissingRecording, ReplayTransport
from support.scripted import ScriptedTransport

needs_craft = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")
EXPLORERS = 5
TURNS = 4
CANARY = "sk-ant-canary-0048-never-in-a-recording"


def ask(text: str, effort: str = "high") -> dict:
    """The params the gateway sends for one turn, with one user message."""
    return {
        "model": "claude-opus-5-5",
        "max_tokens": 32000,
        "system": [{"type": "text", "text": "sistema"}],
        "messages": [{"role": "user", "content": text}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
        "cache_control": {"type": "ephemeral"},
    }


def said(response: dict) -> str:
    return response["content"][0]["text"]


def last(params: dict) -> str:
    return params["messages"][-1]["content"]


class Echo:
    """A stand-in for the live API: each answer names its request and its place in the order of answers.

    With a barrier, every call waits inside the model until all of them are in flight together.
    """

    def __init__(self, barrier: threading.Barrier | None = None) -> None:
        self.barrier = barrier
        self.answered = 0
        self.lock = threading.Lock()

    def count_tokens(self, params: dict) -> int:
        return 100 + len(last(params))

    def stream(self, params: dict) -> dict:
        if self.barrier is not None:
            self.barrier.wait()
        with self.lock:
            self.answered += 1
            order = self.answered
        # A long answer, as a real turn with its thinking is: a torn append would show up as a broken line.
        text = f"risposta {order} a {last(params)}"
        return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "pad": "x" * 200_000}


def test_parallel_recording_replays_in_any_order(tmp_path: Path) -> None:
    """Five explorers record at once: no line interleaves, and replay answers each request in any order."""
    cassette = tmp_path / "cassettes" / "p" / "1.jsonl"
    live = Echo(threading.Barrier(EXPLORERS, timeout=10))  # the recorder never serializes the model's calls
    recorder = RecordingTransport(live, cassette)
    asked = [ask(f"esploratore {i}, turno {n}") for i in range(EXPLORERS) for n in range(TURNS)]

    def explore(i: int) -> dict[str, str]:
        return {last(params): said(recorder.stream(params)) for params in asked[i * TURNS : (i + 1) * TURNS]}

    with ThreadPoolExecutor(EXPLORERS) as pool:
        live_answers = {k: v for answers in pool.map(explore, range(EXPLORERS)) for k, v in answers.items()}
    live.barrier = None
    again = [said(recorder.stream(ask("di nuovo"))) for _ in range(2)]

    records = [json.loads(line) for line in cassette.read_text(encoding="utf-8").splitlines()]
    assert len(records) == EXPLORERS * TURNS + 2
    assert {record["kind"] for record in records} == {"stream"}

    replay = ReplayTransport(cassette)
    shuffled = list(asked)
    random.Random(48).shuffle(shuffled)
    for params in shuffled:
        assert said(replay.stream(params)) == live_answers[last(params)]
    repeated = [said(replay.stream(ask("di nuovo"))) for _ in range(2)]
    assert repeated == again  # identical requests get their answers in the order they were recorded
    with pytest.raises(MissingRecording):
        replay.stream(ask("di nuovo"))


def test_count_tokens_is_replayed(tmp_path: Path) -> None:
    """The gateway sends `count_tokens` and `stream` the same params: each is served by its own kind."""
    cassette = tmp_path / "1.jsonl"
    recorder = RecordingTransport(Echo(), cassette)
    params = ask("quanto costa questo turno")
    counted = recorder.count_tokens(params)
    answered = said(recorder.stream(params))

    replay = ReplayTransport(cassette)
    assert said(replay.stream(params)) == answered
    assert replay.count_tokens(params) == counted == 100 + len("quanto costa questo turno")
    with pytest.raises(MissingRecording):
        replay.count_tokens(params)


def test_the_key_is_the_canonical_request() -> None:
    """Five fields make the key, as sorted, compact UTF-8 JSON. Limit, thinking and cache do not."""
    assert (
        request_key({"model": "perché", "messages": []})
        == hashlib.sha256('{"messages":[],"model":"perché"}'.encode()).hexdigest()
    )
    base = ask("ciao")
    reordered = {**base, "system": [{"text": "sistema", "type": "text"}]}
    assert request_key(reordered) == request_key(base)
    for field, value in [
        ("model", "claude-sonnet-5-5"),
        ("system", [{"type": "text", "text": "altro"}]),
        ("tools", [{"name": "consegna"}]),
        ("messages", [{"role": "user", "content": "addio"}]),
        ("output_config", {"effort": "low"}),
    ]:
        assert request_key({**base, field: value}) != request_key(base), field
    for field, value in [("max_tokens", 128000), ("thinking", {}), ("cache_control", None)]:
        assert request_key({**base, field: value}) == request_key(base), field


class Failing:
    def count_tokens(self, params: dict) -> int:
        raise ValueError("count_tokens non risponde")

    def stream(self, params: dict) -> dict:
        raise ValueError("JSON degli strumenti illeggibile")


def test_a_failed_call_leaves_no_line(tmp_path: Path) -> None:
    cassette = tmp_path / "1.jsonl"
    recorder = RecordingTransport(Failing(), cassette)
    with pytest.raises(ValueError, match="illeggibile"):
        recorder.stream(ask("ciao"))
    with pytest.raises(ValueError, match="non risponde"):
        recorder.count_tokens(ask("ciao"))
    assert not cassette.exists()


def test_a_line_is_appended_only_under_the_lock(tmp_path: Path) -> None:
    """The file system may not tear one write here, but the recorder never relies on it: each append holds
    the recorder's one lock."""
    cassette = tmp_path / "1.jsonl"
    recorder = RecordingTransport(Echo(), cassette)
    with recorder._lock:
        worker = threading.Thread(target=recorder.stream, args=(ask("ciao"),))
        worker.start()
        worker.join(timeout=1)
        waiting = worker.is_alive()  # answered by the model, its line waits for the lock
        written = cassette.exists()
    worker.join(timeout=10)
    assert waiting and not written
    assert len(cassette.read_text(encoding="utf-8").splitlines()) == 1


SSE = [
    {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant",
     "model": "claude-opus-5-5", "content": [], "stop_reason": None, "stop_sequence": None,
     "usage": {"input_tokens": 10, "output_tokens": 1}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Ciao"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
     "usage": {"output_tokens": 4}},
    {"type": "message_stop"},
]  # fmt: skip


def test_a_recording_never_contains_the_key(tmp_path: Path) -> None:
    """The real SDK sends the key on both calls, httpx2.MockTransport answers, and no recording holds it."""
    sent: list[httpx2.Request] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        if request.url.path == "/v1/messages/count_tokens":
            return httpx2.Response(200, json={"input_tokens": 1000})
        stream = b"".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n".encode() for e in SSE)
        headers = {"content-type": "text/event-stream", "request-id": "req_registrata"}
        return httpx2.Response(200, headers=headers, content=stream)

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(answer))
    client = anthropic.Anthropic(api_key=CANARY, http_client=http, max_retries=0)
    cassette = tmp_path / "1.jsonl"
    recorder = RecordingTransport(AnthropicTransport(client=client), cassette)

    assert recorder.count_tokens(ask("ciao")) == 1000
    assert said(recorder.stream(ask("ciao"))) == "Ciao"

    assert [request.headers["x-api-key"] for request in sent] == [CANARY, CANARY]
    text = cassette.read_text(encoding="utf-8")
    assert [json.loads(line)["kind"] for line in text.splitlines()] == ["count_tokens", "stream"]
    assert CANARY not in text


def test_a_missing_recording_names_the_turn(tmp_path: Path) -> None:
    """The first request the recording does not hold stops the replay and says which turn it was."""
    cassette = tmp_path / "1.jsonl"
    RecordingTransport(Echo(), cassette).stream(ask("il turno registrato"))
    other = ask("un turno che la registrazione non conosce")

    with pytest.raises(MissingRecording) as missed:
        ReplayTransport(cassette).stream(other)

    assert missed.value.key == request_key(other)
    summary = missed.value.summary
    assert "stream" in summary
    assert "claude-opus-5-5" in summary
    assert "1 messages" in summary
    assert "un turno che la registrazione non conosce" in summary


# A whole session, recorded and then replayed on a fresh data folder.


def use(name: str, tool_id: str, **arguments: object) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def turn(*blocks: dict) -> dict:
    return {
        "content": list(blocks),
        "stop_reason": "tool_use",
        "model": "claude-opus-5-5",
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


def settings(folder: Path) -> Settings:
    return Settings(data_dir=folder / "data", projects_dir=folder / "projects", _env_file=None)  # type: ignore[call-arg]


MASTER, SVG = "source/segno.vectorcraft", "exports/segno.svg"
OUTPUTS = [MASTER, SVG, "construction.md"]
CHECKS = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
DRAW = [
    {"command": "path.create", "params": {"d": "M10 90 L50 10 L90 90 Z"}},
    {"command": "select.set", "params": {"ids": [2]}},
    {"command": "paint.setStroke", "params": {"none": True}},
    {"command": "paint.setFill", "params": {"color": "#111111"}},
]


def to_the_final_gate() -> list[dict]:
    """The full project of test_agent_flow.py, from the brief to the client's final gate."""
    production = {
        "title": "Segno",
        "request": "Il segno del forno",
        "type": "produzione",
        "assignee": "identity-designer",
        "outputs": OUTPUTS,
        "checks": {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "svg_parity"]},
        "media": ["vettoriale"],
        "exempt": {"construction.md": "documento di costruzione del segno"},
    }
    qa = {
        "title": "QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [SVG],
        "checks": {"*.svg": ["svg_audit"]},
    }
    review = {
        "title": "Critica",
        "request": "Giudica",
        "type": "revisione",
        "assignee": "critic",
        "outputs": [SVG],
        "checks": {"*.svg": ["critique"]},
    }
    why = (
        "Rispetto alla versione precedente il segno ha un'apertura più netta e regge meglio a piccola scala."
    )
    return [
        turn(use("open_ticket", "d1", **production)),
        turn(use("hand_off", "d2", note="attendo il segno")),
        turn(use("craft_run", "p1", document=MASTER, steps=DRAW)),
        turn(use("export_master", "p2", master=MASTER, output=SVG)),
        turn(use("compute", "p3", code="print(1)")),
        turn(use("write_file", "p4", path="construction.md", content="unità u")),
        turn(use("write_file", "p5", path="source/precedente.md", content="v0")),
        turn(
            use("run_check", "p6", check="master_open", file=MASTER),
            use("run_check", "p7", check="svg_audit", file=SVG),
            use("run_check", "p8", check="svg_parity", file=SVG),
        ),
        turn(use("deliver", "p9", note="segno pronto", verdict=None)),
        turn(use("open_ticket", "d3", **qa), use("open_ticket", "d4", **review)),
        turn(use("hand_off", "d5", note="attendo le revisioni")),
        turn(use("run_check", "q1", check="svg_audit", file=SVG)),
        turn(use("deliver", "q2", note="tutto regolare", verdict="READY")),
        turn(use("render", "c1", path=SVG)),
        turn(use("view_image", "c2", path="proofs/render/exports_segno.svg.png")),
        turn(use("judge", "c3", file=SVG, compare=["source/precedente.md"], why=why, result="PASS")),
        turn(use("deliver", "c4", note="regge", verdict="READY")),
        turn(
            use("accept_ticket", "d6", ticket="T-0002"),
            use("accept_ticket", "d7", ticket="T-0003"),
            use("accept_ticket", "d8", ticket="T-0004"),
        ),
        turn(use("deliver", "d9", note="consegnato", verdict=None)),
    ]


AFTER_THE_REJECTION = [
    turn(use("block", "d10", reason="il cliente vuole un altro segno: serve un brief nuovo"))
]


def delivered(row: TicketRow) -> dict[str, str]:
    """The delivered files and their hashes. VectorCraft stamps each master with the clock (`"created"`, in
    seconds), so a master's hash changes from run to run; no request carries it, and replay does not miss."""
    files = json.loads(row.delivered_json)
    return {name: "" if name.endswith(".vectorcraft") else digest for name, digest in files.items()}


def ledger_of(session: Session, project: str) -> dict:
    """What a run leaves in the registry, without the times."""
    ledger = session.ledger
    tickets = ledger.tickets(project)
    return {
        "tickets": [(t.id, t.status, t.verdict, delivered(t)) for t in tickets],
        "events": [[(e.ticket_id, e.actor, e.action) for e in ledger.history(t.id)] for t in tickets],
        "usage": [(row.run, row.ticket_id, row.role, row.stop_reason) for row in ledger.usage(project)],
    }


def kinds(cassette: Path) -> list[str]:
    return [json.loads(line)["kind"] for line in cassette.read_text(encoding="utf-8").splitlines()]


@needs_craft
def test_a_recorded_run_replays_to_the_same_ledger(tmp_path: Path) -> None:
    """Recorded once with real Craft tools, the run replays on another data folder to the same registry."""
    brief = tmp_path / "brief.txt"
    brief.write_text("Un segno per un forno di quartiere", encoding="utf-8")
    live = settings(tmp_path / "live")
    first = to_the_final_gate()
    session = open_session(live, ScriptedTransport(first + AFTER_THE_REJECTION), record=True)
    session.start("forno", brief, OUTPUTS, CHECKS, budget=1000.0, explore=False)
    assert session.pending("forno")[0].gate == "final"
    session.decide("forno", False, "Non è il forno che conosco")
    recorded = ledger_of(session, "forno")

    run, then = (live.layout.cassette(ProjectName("forno"), seq) for seq in (1, 2))
    assert kinds(run).count("stream") == len(first)  # each run its own cassette: the second is not nested
    assert kinds(then) == ["count_tokens", "stream"]

    replayed = settings(tmp_path / "replayed")
    start = open_session(replayed, (served := ReplayTransport(run)))
    start.start("forno", brief, OUTPUTS, CHECKS, budget=1000.0, explore=False)
    decide = open_session(replayed, (served_then := ReplayTransport(then)))
    decide.decide("forno", False, "Non è il forno che conosco")

    assert served.left() == served_then.left() == 0  # the replay made every recorded call, and no other
    assert ledger_of(decide, "forno") == recorded
    assert recorded["usage"] and recorded["tickets"]
    assert not (replayed.data_dir / "cassettes").exists()


def cli_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Data and project folders of the test's own, and no .env: the CLI builds its settings from here."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "data"


BLOCK_AT_ONCE = {
    "content": [
        {"type": "tool_use", "id": "t1", "name": "block", "input": {"reason": "prova della registrazione"}}
    ],
    "stop_reason": "tool_use",
    "model": "claude-opus-5-5",
    "usage": {"input_tokens": 100, "output_tokens": 20},
}


@pytest.mark.parametrize("record", [False, True])
def test_agency_run_records_only_when_asked(
    record: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--record` writes the run's cassette under the data folder; without it no cassette folder appears."""
    data = cli_data(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("Un segno per un forno di quartiere", encoding="utf-8")
    transport = ScriptedTransport([BLOCK_AT_ONCE])
    monkeypatch.setattr(
        "agency.runtime.open_session",
        lambda settings, record=False: open_session(settings, transport, record=record),
    )

    assert cli.main(["run", "forno", str(brief), "--budget", "12", *(["--record"] if record else [])]) == 0

    if record:
        assert kinds(data / "cassettes" / "forno" / "1.jsonl") == ["count_tokens", "stream"]
    else:
        assert not (data / "cassettes").exists()


class Opened(Exception):
    """The command reached `open_session`: what it asked for is all this test needs."""


@pytest.mark.parametrize(
    "command",
    [
        ["run", "forno", "brief.md", "--budget", "5"],
        ["resume", "forno"],
        ["decide", "forno", "--approve", "--text", "ok"],
    ],
)
@pytest.mark.parametrize("flag", [[], ["--record"]])
def test_every_working_command_hands_record_to_its_session(
    command: list[str], flag: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Ledger(cli_data(tmp_path, monkeypatch) / "ledger.sqlite").set_project("forno", 5.0)
    asked: list[bool] = []

    def opened(settings: Settings, transport: object = None, record: bool = False) -> Session:
        asked.append(record)
        raise Opened

    monkeypatch.setattr("agency.runtime.open_session", opened)
    with pytest.raises(Opened):
        cli.main([*command, *flag])
    assert asked == [bool(flag)]
