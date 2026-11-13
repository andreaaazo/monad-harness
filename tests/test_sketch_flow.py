"""The exploration with real Craft and recorded answers: no API call."""

from __future__ import annotations

import json
import re
import shutil
import threading
from collections import defaultdict
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from agency.artifacts import FileStore
from agency.contracts.concept import ConceptCard
from agency.contracts.gate import ConceptGate
from agency.contracts.project import ProjectName
from agency.contracts.run import Fingerprint, changes
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.gateway import BudgetExceeded
from agency.insights.adapters.ledger import ReadOnlyLedger
from agency.insights.domain import derive_phase
from agency.ledger import Ledger
from agency.ledger.models import ConceptRow
from agency.qa import delivery
from agency.runtime import Session, open_session
from agency.tools import board, presentation
from agency.tools.craft import CommandIndex
from agency.tools.files import sha256
from agency.tools.sandbox import Sandbox
from agency.tools.surface import (
    EXPLORE,
    PLAN,
    PRESENT,
    PROPOSAL,
    SELECT,
    TOOLS,
    Toolbox,
    ToolContext,
    tools_for,
)
from support.concepts import open_idea
from support.scripted import turn
from support.settings import settings

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")
MASTER, SVG = "source/segno.vectorcraft", "exports/segno.svg"
OUTPUTS = [MASTER, SVG, "construction.md"]
CHECKS = {"*.vectorcraft": ["master_open"], "*.svg": ["svg_audit", "critique"]}
SEEN = "Segno nero pieno e centrato, bordi netti, l'idea si legge al primo sguardo."
WHY = "Rispetto allo schizzo il segno ha spessori coerenti e regge meglio alle dimensioni piccole."
DRAW = [
    {"command": "path.create", "params": {"d": "M10 90 L50 10 L90 90 Z"}},
    {"command": "select.set", "params": {"ids": [2]}},
    {"command": "paint.setStroke", "params": {"none": True}},
    {"command": "paint.setFill", "params": {"color": "#111111"}},
]


def use(name: str, **arguments: object) -> dict:
    use.count += 1  # type: ignore[attr-defined]
    return {"type": "tool_use", "id": f"toolu_{use.count}", "name": name, "input": arguments}  # type: ignore[attr-defined]


use.count = 0  # type: ignore[attr-defined]


def card(text: str) -> dict:
    return {
        "concept": text,
        "client_fact": "Raddrizza le ruote a mano",
        "why_not_obvious": "Evita la ruota dentata",
        "drawing": "Un triangolo pieno",
        "substitution": "Vale solo per chi ripara",
    }


class Router:
    """Answers per instance: the order among parallel agents does not matter."""

    def __init__(self, script: dict[str, list[dict]]) -> None:
        self.script = script
        self.requests: dict[str, list[dict]] = defaultdict(list)
        self.lock = threading.Lock()

    def count_tokens(self, params: dict) -> int:
        return 1000

    def key(self, params: dict) -> str:
        first = params["messages"][0]["content"]
        ticket = re.search(r"TICKET (T-\d+)", first).group(1)  # type: ignore[union-attr]
        system = params["system"][0]["text"]
        marks = (
            ("piano dell'esplorazione", ":plan"),
            ("scelta interna", ":select"),
            ("presentazione al cliente", ":present"),
        )
        for mark, suffix in marks:
            if mark in system:
                return ticket + suffix
        return ticket

    def stream(self, params: dict) -> dict:
        key = self.key(params)
        with self.lock:
            self.requests[key].append(json.loads(json.dumps(params)))
            if not self.script.get(key):
                last = str(params["messages"][-1]["content"])[:600]
                raise AssertionError(f"no answers left for {key}: {last}")
            return self.script[key].pop(0)


BUDGET = 1000.0  # the cap every test declares at the start, like agency run --budget (ADR-0043)


def brief(tmp_path: Path) -> Path:
    path = tmp_path / "brief.md"
    path.write_text("Un segno per un'officina che ripara")
    return path


def plan_arguments(levers: int = 3) -> dict:
    names = ["il nome", "il gesto", "la materia", "le persone", "la convenzione rovesciata"][:levers]
    return {
        "levers": [{"lever": name} for name in names],
        "assets": ["merlo"],
        "excluded": ["ruota dentata", "chiave inglese", "ciclista stilizzato"],
        "applications": [{"name": "timbro", "size": "16 mm"}, {"name": "insegna", "size": "80 cm"}],
    }


def plan_turn(levers: int = 3) -> list[dict]:
    return [turn(use("plan_exploration", **plan_arguments(levers)))]


def explorer_turns(letter: str) -> list[dict]:
    master, sheet, png = f"schizzi-{letter}.vectorcraft", f"foglio-{letter}.png", f"schizzo-{letter}.png"
    return [
        turn(use("craft_run", document=master, steps=DRAW)),
        turn(
            use("export_master", master=master, output=sheet), use("export_master", master=master, output=png)
        ),
        turn(use("view_image", path=sheet), use("view_image", path=png)),
        turn(
            use("observe", file=sheet, seen=SEEN),
            use("observe", file=png, seen=SEEN),
            use("run_check", check="master_open", file=master),
        ),
        turn(use("submit_concept", **card(f"Idea {letter}"))),
    ]


def board_turns(letters: str = "XYZ", failing: str = "") -> list[dict]:
    ratings = [
        {"letter": letter, "first_look": f"Si vede {letter}", "passes": letter not in failing}
        for letter in letters
    ]
    verdict = "READY" if set(letters) - set(failing) else "REVISE"
    return [
        turn(use("view_image", path="tavola.png")),
        turn(use("rate_board", ratings=ratings)),
        turn(use("observe", file="tavola.png", seen=SEEN, check="board_review")),
        turn(use("write_file", path="reviews/selezione.md", content="X, poi Y")),
        turn(use("deliver", note="primo sguardo fatto", verdict=verdict)),
    ]


def proposal_turns(anon: str) -> list[dict]:
    letter = anon.lower()
    master, svg, png = f"proposta-{letter}.vectorcraft", f"proposta-{letter}.svg", f"proposta-{letter}.png"
    application = f"applicazioni-{letter}/timbro.png"
    return [
        turn(use("view_image", path="schizzo.png")),
        turn(use("craft_run", document=master, steps=DRAW)),
        turn(
            use("export_master", master=master, output=svg),
            use("export_master", master=master, output=png),
            use("export_master", master=master, output=application),
        ),
        turn(use("view_image", path=png), use("view_image", path=application)),
        turn(use("observe", file=png, seen=SEEN), use("observe", file=application, seen=SEEN)),
        turn(
            use("run_check", check="master_open", file=master),
            use("run_check", check="svg_audit", file=svg),
        ),
        turn(use("deliver", note="proposta pronta", verdict=None)),
    ]


def present_turn(*letters: str, round_: int = 1, pages: int = 0) -> list[dict]:
    """Draft, a look at each page, sending: three pages per proposal plus the recommendation."""
    texts = [
        {"letter": letter, "title": f"Titolo {letter}", "idea": "Idea", "why": "Perché sì", "risk": "Limite"}
        for letter in letters
    ]
    views = [
        use("view_image", path=f"presentation/r{round_}/pagina-{number}.png")
        for number in range(1, (pages or 3 * len(letters) + 1) + 1)
    ]
    return [
        turn(use("draft_presentation", proposals=texts, recommended=letters[0], reasons="Regge meglio")),
        turn(*views),
        turn(use("present_concepts")),
    ]


def exploration(first: int = 2, count: int = 3) -> dict[str, list[dict]]:
    """Tickets from `first` on: the explorers, then the board."""
    script: dict[str, list[dict]] = {}
    for offset, letter in enumerate("abcde"[:count]):
        script[f"T-{first + offset:04d}"] = explorer_turns(letter)
    script[f"T-{first + count:04d}"] = board_turns("VWXYZ"[-count:])
    return script


def to_the_gate() -> dict[str, list[dict]]:
    """From the start to the presentation: two developed proposals, T-0006 and T-0007."""
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0001:select"] = [turn(use("select_concepts", chosen=["X", "Y"], reasons="Si leggono da sole"))]
    script["T-0006"] = proposal_turns("X")
    script["T-0007"] = proposal_turns("Y")
    script["T-0001:present"] = present_turn("X", "Y")
    return script


def full_script() -> dict[str, list[dict]]:
    production = [  # the master starts from the approved proposal
        turn(use("export_master", master=MASTER, output=SVG)),
        turn(use("write_file", path="construction.md", content="unità u")),
        turn(
            use("run_check", check="master_open", file=MASTER),
            use("run_check", check="svg_audit", file=SVG),
        ),
        turn(use("deliver", note="costruito", verdict=None)),
    ]
    qa_spec = {
        "title": "Verifica QA",
        "request": "Verifica",
        "type": "qa",
        "assignee": "qa-inspector",
        "outputs": [SVG],
        "checks": {"*.svg": ["svg_audit"]},
    }
    review_spec = {
        "title": "Critica",
        "request": "Giudica",
        "type": "revisione",
        "assignee": "critic",
        "outputs": [SVG],
        "checks": {"*.svg": ["critique"]},
    }
    script = to_the_gate()
    script["T-0008"] = production
    script["T-0001"] = [
        turn(use("open_ticket", **qa_spec), use("open_ticket", **review_spec)),
        turn(use("hand_off", note="attendo")),
        turn(
            use("accept_ticket", ticket="T-0008"),
            use("accept_ticket", ticket="T-0009"),
            use("accept_ticket", ticket="T-0010"),
        ),
        turn(use("deliver", note="consegnato", verdict=None)),
    ]
    script["T-0009"] = [
        turn(use("run_check", check="svg_audit", file=SVG)),
        turn(use("deliver", note="regolare", verdict="READY")),
    ]
    script["T-0010"] = [
        turn(use("render", path=SVG)),
        turn(use("view_image", path="proofs/render/exports_segno.svg.png")),
        turn(use("judge", file=SVG, compare=["construction.md"], why=WHY, result="PASS")),
        turn(use("deliver", note="regge", verdict="READY")),
    ]
    return script


def context(tmp_path: Path, role: str = "critic", ticket: str = "T-1", round_: int = 1) -> ToolContext:
    ledger = Ledger(tmp_path / "l.sqlite")
    return ToolContext(
        role,
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        round=round_,
        settings=settings(tmp_path),
    )


def concept_gate(session: Session, project: str) -> ConceptGate:
    (gate,) = session.pending(project)
    assert isinstance(gate, ConceptGate)
    return gate


def options(session: Session, project: str) -> list[str]:
    return concept_gate(session, project).options


def test_client_only_sees_developed_proposals_then_production_starts(tmp_path: Path) -> None:
    config = settings(tmp_path)
    transport = Router(full_script())
    session = open_session(config, transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    gate = session.pending("officina")[0]
    assert isinstance(gate, ConceptGate)
    assert (gate.gate, gate.options, gate.recommended) == ("concept", ["X", "Y"], "X")
    assert gate.files == ["presentation/r1/presentazione.pdf"]
    work = config.project_dir(ProjectName("officina")) / "work"
    assert (work / gate.files[0]).read_bytes()[:4] == b"%PDF"
    concepts = session.ledger.concepts("officina", 1)
    assert {row.anon: row.status for row in concepts} == {"X": "proposta", "Y": "proposta", "Z": "schizzo"}
    titles = [session.ledger.spec(row.id).title for row in session.ledger.tickets("officina")]
    assert "Proposta X r1" in titles and not any(title.startswith("Rifinitura") for title in titles)
    session.decide("officina", True, "Mi piace la X", "X")
    assert session.pending("officina")[0].gate == "final"
    assert session.ledger.gates("officina")[0].choice == "X"
    after = {row.anon: row.status for row in session.ledger.concepts("officina", 1)}
    assert after == {"X": "scelta", "Y": "proposta", "Z": "schizzo"}  # production marks the client's choice
    spec = session.ledger.spec("T-0008")
    chosen = next(row for row in concepts if row.anon == "X")
    assert chosen.card_json in spec.request and "proposals/r1/x/proposta-x.png" in spec.inputs
    session.decide("officina", True, "Approvato")
    assert session.ledger.status("T-0001")[0] is Status.ACCEPTED
    assert session.ledger.verify_chain()
    assert transport.requests["T-0002"][0]["output_config"] == {"effort": "high"}
    assert transport.requests["T-0006"][0]["output_config"] == {"effort": "high"}


def test_a_crash_after_the_concept_decision_records_one_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On resume the gate node runs again from the start: the client's decision is recorded once (TST-015)."""
    session = open_session(settings(tmp_path), Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    record = session.ledger.add_gate

    def die_after_recording(row: object) -> None:
        record(row)  # type: ignore[arg-type]
        raise RuntimeError("the process died after recording the gate")

    monkeypatch.setattr(session.ledger, "add_gate", die_after_recording)
    with pytest.raises(RuntimeError, match="died after recording the gate"):
        session.decide("officina", True, "Mi piace la X", "X")
    monkeypatch.setattr(session.ledger, "add_gate", record)
    session.decide("officina", True, "Mi piace la X", "X")
    assert session.pending("officina")[0].gate == "final"
    concept = [row for row in session.ledger.gates("officina") if row.gate == "concept"]
    assert [(row.approved, row.choice) for row in concept] == [(True, "X")]


def test_explorers_think_and_draw_in_one_instance(tmp_path: Path) -> None:
    transport = Router(to_the_gate())
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.spec("T-0002").outputs) == 4
    names = {tool["name"] for tool in transport.requests["T-0002"][0]["tools"]}
    assert {"craft_run", "view_image", "submit_concept"} <= names
    assert "Cerchi un segno **disegnando**" in transport.requests["T-0002"][0]["system"][0]["text"]


def test_effort_can_be_lowered_to_medium(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path, explorer_effort="medium"), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert transport.requests["T-0003"][0]["output_config"] == {"effort": "medium"}


def test_explorer_cannot_close_without_having_looked(tmp_path: Path) -> None:
    script = {"T-0001:plan": plan_turn(2)}
    script["T-0002"] = [
        turn(use("submit_concept", **card("Solo parole"))),
        turn(use("block", reason="prova")),
    ]
    script["T-0003"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    refused = transport.requests["T-0002"][1]["messages"][-1]["content"][0]
    assert refused["is_error"] and "consegna rifiutata" in refused["content"]


def test_finisher_starts_from_the_approved_proposal(tmp_path: Path) -> None:
    config = settings(tmp_path)
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="prova finita"))]
    script["T-0001"] = [turn(use("block", reason="prova finita"))]
    session = open_session(config, Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "La Y", "Y")
    work = config.project_dir(ProjectName("officina")) / "work"
    assert (work / MASTER).read_bytes() == (work / "proposals/r1/y/proposta-y.vectorcraft").read_bytes()


def test_proposals_run_in_parallel(tmp_path: Path) -> None:
    together = threading.Barrier(2, timeout=20)

    class Meeting(Router):
        def stream(self, params: dict) -> dict:
            key = self.key(params)
            if key in ("T-0006", "T-0007") and not self.requests[key]:
                together.wait()
            return super().stream(params)

    session = open_session(settings(tmp_path), Meeting(to_the_gate()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    spec = session.ledger.spec("T-0006")
    assert "timbro: 16 mm" in spec.request
    assert spec.workspace == "proposals/r1/x"


def test_studio_can_drop_a_proposal_before_the_client(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0001:present"] = present_turn("Y")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert options(session, "officina") == ["Y"]


def test_failed_proposal_does_not_stop_the_other(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0006"] = [turn(use("block", reason="Non regge alle dimensioni richieste"))]
    script["T-0001:present"] = present_turn("Y")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert options(session, "officina") == ["Y"]


def test_weak_proposals_go_back_to_exploration(tmp_path: Path) -> None:
    script = to_the_gate()
    empty = {"proposals": [], "recommended": None, "reasons": "Nessuna è presentabile"}
    script["T-0001:present"] = [turn(use("draft_presentation", **empty))]
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert session.pending("officina") == []
    assert "Nessuna è presentabile" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_presentation_has_pages_for_each_proposal_and_the_recommendation(tmp_path: Path) -> None:
    mark = tmp_path / "segno.png"
    Image.new("RGB", (400, 400), (0, 0, 0)).save(mark)
    items = [
        presentation.Proposal(
            letter, "Titolo", "Idea " * 30, "Perché " * 30, "Limite " * 10, mark, (mark, mark)
        )
        for letter in ("X", "Y")
    ]
    pages = presentation.build(items, "X", "Regge meglio", tmp_path / "out")
    assert (tmp_path / "out/presentazione.pdf").read_bytes()[:4] == b"%PDF"
    assert len(pages) == 7  # mark, applications and reasons for each proposal, then the recommendation
    with Image.open(tmp_path / "out/pagina-1.png") as page:
        assert max(page.size) <= 1600


def test_presentation_font_has_italian_accents() -> None:
    def drawn(text: str) -> bytes:
        image = Image.new("L", (80, 80), 255)
        ImageDraw.Draw(image).text((10, 10), text, fill=0, font=presentation.font(40))
        return image.tobytes()

    missing = drawn("\U000e0000")
    assert all(drawn(letter) != missing for letter in "àèéìòùÈ")


def test_present_refuses_what_was_not_developed(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    open_idea(
        ctx.ledger,
        ConceptRow(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"),
    )
    open_idea(
        ctx.ledger,
        ConceptRow(project="p", round=1, letter="b", lever="l", idea_ticket="", anon="Y", status="schizzo"),
    )
    box = Toolbox(ctx, [TOOLS["draft_presentation"]])
    folder = tmp_path / "proposals/r1/x"
    folder.mkdir(parents=True)
    Image.new("RGB", (300, 200), (20, 20, 20)).save(folder / "proposta-x.png")
    text = {"letter": "Y", "title": "T", "idea": "I", "why": "W", "risk": "R"}
    assert box.call("a", "draft_presentation", {"proposals": [text], "recommended": "Y", "reasons": "r"})[
        "is_error"
    ]
    text["letter"] = "X"
    assert box.call("b", "draft_presentation", {"proposals": [text], "recommended": "Y", "reasons": "r"})[
        "is_error"
    ]
    done = box.call("c", "draft_presentation", {"proposals": [text], "recommended": "X", "reasons": "r"})
    assert not done.get("is_error")


def test_five_directions_run_together_and_reach_the_board(tmp_path: Path) -> None:
    together = threading.Barrier(5, timeout=20)

    class Meeting(Router):
        def stream(self, params: dict) -> dict:
            key = self.key(params)
            if key in ("T-0002", "T-0003", "T-0004", "T-0005", "T-0006") and not self.requests[key]:
                together.wait()  # it times out unless all five run together
            return super().stream(params)

    script = exploration(count=5)
    script["T-0001:plan"] = plan_turn(5)
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    config = settings(tmp_path)
    session = open_session(config, Meeting(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    concepts = session.ledger.concepts("officina", 1)
    assert sorted(row.anon for row in concepts) == list("VWXYZ")
    assert {session.ledger.spec(row.idea_ticket).assignee for row in concepts} == {
        f"direction-{letter}" for letter in "abcde"
    }
    work = config.project_dir(ProjectName("officina")) / "work"
    with Image.open(work / "board/r1/tavola.png") as image:
        assert max(image.size) <= 1600
    assert sorted(path.stem for path in (work / "board/r1/fogli").glob("*.png")) == list("VWXYZ")


def test_number_of_directions_can_go_back_to_three(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn(5)
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path, explorers=3), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.concepts("officina", 1)) == 3
    assert "Esploratori disponibili: 3" in transport.requests["T-0001:plan"][0]["messages"][0]["content"]


def test_explorers_do_not_see_each_other(tmp_path: Path) -> None:
    script = {
        "T-0001:plan": plan_turn(2),
        "T-0002": [turn(use("read_file", path="../b/brief.md")), turn(use("block", reason="prova finita"))],
        "T-0003": [turn(use("block", reason="prova finita"))],
    }
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    result = transport.requests["T-0002"][1]["messages"][-1]["content"][0]
    assert result["is_error"] and "fuori" in result["content"]


def test_each_phase_has_only_its_tools() -> None:
    base = TicketSpec(
        title="Esplorazione",
        request="r",
        type=TicketType.SKETCH,
        sender="d",
        assignee="c",
        outputs=["a"],
        checks={"a": ["master_open"]},
        media=[Medium.VECTOR],
    )
    assert {tool.name for tool in tools_for("direction-a", base)} == set(EXPLORE)
    proposal = base.model_copy(update={"type": TicketType.PROPOSAL})
    assert {tool.name for tool in tools_for("identity-designer", proposal)} == set(PROPOSAL)
    assert {t.name for t in tools_for("design-director", base, "plan")} == set(PLAN)
    assert {t.name for t in tools_for("design-director", base, "select")} == set(SELECT)
    assert {t.name for t in tools_for("design-director", base, "present")} == set(PRESENT)
    assert all(name in TOOLS for name in (*EXPLORE, *PLAN, *SELECT, *PRESENT, *PROPOSAL))


def test_concept_card_schema_is_complete() -> None:
    assert set(ConceptCard.model_json_schema()["required"]) == set(card("x"))


def test_no_limit_on_the_number_of_tools(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x")
    box = Toolbox(context(tmp_path), [TOOLS["read_file"]])
    results = [box.call(f"c{n}", "read_file", {"path": "a.md"}) for n in range(200)]
    assert not any(result.get("is_error") for result in results)


def test_number_of_images_never_blocks_the_work(tmp_path: Path) -> None:
    box = Toolbox(context(tmp_path), [TOOLS["view_image"]])
    for number in range(60):
        Image.new("RGB", (20, 20), (number, 0, 0)).save(tmp_path / f"i{number}.png")
        assert not box.call(f"c{number}", "view_image", {"path": f"i{number}.png"}).get("is_error")


def test_agents_never_hear_about_budget(tmp_path: Path) -> None:
    transport = Router(to_the_gate())
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=1000)
    calls = [call for calls in transport.requests.values() for call in calls]
    assert calls
    for call in calls:  # the tool schemas hold `$ref`: what counts is what the agent reads
        readable = json.dumps([call["system"], call["messages"]], ensure_ascii=False).lower()
        assert "budget" not in readable and "quota" not in readable
        assert " $" not in readable
        descriptions = [tool["description"].lower() for tool in call["tools"]]
        assert not any("budget" in text or "quota" in text for text in descriptions)


def test_client_chooses_model_and_effort_for_the_whole_project(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start(
        "officina", brief(tmp_path), OUTPUTS, CHECKS, budget=9, model="claude-sonnet-5-5", effort="medium"
    )
    sent = transport.requests["T-0003"][0]
    assert sent["model"] == "claude-sonnet-5-5" and sent["output_config"] == {"effort": "medium"}
    assert transport.requests["T-0001:plan"][0]["model"] == "claude-sonnet-5-5"
    assert session.ledger.project("officina").budget_usd == 9  # type: ignore[union-attr]


def test_budget_end_pauses_the_project_and_an_increase_resumes_it(tmp_path: Path) -> None:
    config = settings(tmp_path)
    session = open_session(config, Router(to_the_gate()))
    with pytest.raises(BudgetExceeded):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=0.09)
    session.ledger.set_budget("officina", 50)
    again = open_session(config, session_transport := Router(to_the_gate()))
    again.resume("officina")
    assert again.pending("officina")[0].gate == "concept"
    assert "T-0001:plan" not in session_transport.requests  # the plan already made is not paid for again


def fingerprints(ledger: Ledger, project: str) -> list[Fingerprint]:
    return [Fingerprint.model_validate_json(row.fingerprint_json) for row in ledger.runs(project)]


def test_every_execution_of_a_project_records_its_fingerprint(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(full_script()))
    session.start(
        "officina",
        brief(tmp_path),
        OUTPUTS,
        CHECKS,
        budget=BUDGET,
        model="claude-sonnet-5-5",
        effort="medium",
    )
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Approvato")
    runs = session.ledger.runs("officina")
    assert [row.command for row in runs] == ["run", "decide", "decide"]
    assert len({row.digest for row in runs}) == 1
    taken = fingerprints(session.ledger, "officina")[0]
    assert (taken.model, taken.effort) == ("claude-sonnet-5-5", "medium")


def test_every_call_knows_its_execution_and_phase(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    first, second = (row.seq for row in session.ledger.runs("officina"))
    usage = session.ledger.usage("officina")
    phases = {run: {row.phase for row in usage if row.run == run} for run in (first, second)}
    assert phases[first] == {
        "director-plan",
        "explorer",
        "critic-board",
        "director-select",
        "proposer",
        "director-present",
    }
    assert phases[second] == {"finisher", "design-director", "qa-inspector", "critic"}
    assert {row.run for row in usage} == {first, second}
    assert all(row.effort in {"high", "medium"} and row.duration_ms is not None for row in usage)


def test_everything_delivered_or_shown_to_the_client_is_kept(tmp_path: Path) -> None:
    config = settings(tmp_path)
    session = open_session(config, Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    (pdf,) = session.pending("officina")[0].files
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Approvato")

    store, ledger = FileStore(config.layout.artifacts), session.ledger
    rows = ledger.artifacts("officina")
    kept = {(row.ticket_id, row.path, row.sha256) for row in rows if row.origin == "consegna"}
    for ticket in ledger.tickets("officina"):
        for path, digest in json.loads(ticket.delivered_json).items():
            assert (ticket.id, path, digest) in kept
            assert store.intact(digest)
    (shown,) = [row for row in rows if row.origin == "presentazione"]
    assert (shown.path, shown.ticket_id, shown.media_type) == (pdf, "T-0001", "application/pdf")
    assert json.loads(ledger.gates("officina")[0].files_json) == {pdf: shown.sha256}
    assert {row.run for row in rows} <= {run.seq for run in ledger.runs("officina")}
    assert all(row.run is not None for row in rows)


def test_a_blocked_plan_ends_the_project_and_says_why(tmp_path: Path) -> None:
    script = {"T-0001:plan": [turn(use("block", reason="manca il nome del cliente"))]}
    session = open_session(settings(tmp_path), Router(script))
    outcome = session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert outcome == "bloccato: manca il nome del cliente"
    assert [row.id for row in session.ledger.tickets("officina")] == ["T-0001"]
    assert session.pending("officina") == []


def test_client_refusing_the_final_work_sends_it_back_with_their_words(tmp_path: Path) -> None:
    script = full_script()
    script["T-0001"].append(turn(use("block", reason="aspetto il nuovo segno")))
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    assert session.pending("officina")[0].gate == "final"

    outcome = session.decide("officina", False, "Il tratto è troppo sottile")

    rework = [event for event in session.ledger.history("T-0001") if event.action == "rework"]
    assert [event.note for event in rework] == ["Il tratto è troppo sottile"]
    assert outcome == "bloccato: aspetto il nuovo segno"


def test_insights_derives_the_phase_the_engine_recorded_for_every_call(tmp_path: Path) -> None:
    """The rule that derives the phase of old calls is the one the engine uses for new ones."""
    config = settings(tmp_path)
    session = open_session(config, Router(full_script()))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    snapshot = ReadOnlyLedger(config.layout.ledger).read()
    tickets, calls = snapshot.tickets, snapshot.usage
    assert len({call.phase for call in calls}) == 10
    for call in calls:
        assert call.phase is not None
        assert derive_phase(call, tickets) == call.phase


def test_resume_with_other_settings_shows_what_changed(tmp_path: Path) -> None:
    session = open_session(settings(tmp_path), Router(to_the_gate()))
    with pytest.raises(BudgetExceeded):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=0.09)
    session.ledger.set_budget("officina", 50)
    again = open_session(settings(tmp_path, explorer_effort="medium"), Router(to_the_gate()))
    again.resume("officina")
    first, second = fingerprints(again.ledger, "officina")
    assert [row.command for row in again.ledger.runs("officina")] == ["run", "resume"]
    assert [(c.part, c.before, c.after) for c in changes(first, second)] == [
        ("explorer_effort", "high", "medium")
    ]


def test_exploration_continues_as_long_as_the_budget_allows(tmp_path: Path) -> None:
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = plan_turn() + plan_turn() + [turn(use("block", reason="prova finita"))]
    empty = {"chosen": [], "reasons": "Nessun segno regge"}
    script["T-0001:select"] = [turn(use("select_concepts", **empty)), turn(use("select_concepts", **empty))]
    script |= {f"T-{6 + n:04d}": explorer_turns("abc"[n]) for n in range(3)}
    script["T-0009"] = board_turns("XYZ", failing="XYZ")
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert len(session.ledger.concepts("officina", 2)) == 3


def test_excluded_cannot_ban_a_client_asset(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    arguments = plan_arguments() | {"excluded": ["sagoma di Merlo nero", "ruota dentata", "chiave inglese"]}
    result = Toolbox(ctx, [TOOLS["plan_exploration"]]).call("a", "plan_exploration", arguments)
    assert result["is_error"] and "risorsa del cliente" in result["content"]


def test_each_lever_goes_to_its_own_direction_in_order(tmp_path: Path) -> None:
    """The first lever goes to direction-a, which draws in folder a under files named a, and so on to e."""
    ctx = context(tmp_path, "design-director")
    ctx.ticket_id = ctx.ledger.open(
        TicketSpec(
            title="Radice",
            request="r",
            type=TicketType.PRODUCTION,
            sender="design-director",
            assignee="design-director",
            outputs=["x.png"],
            checks={"*.png": ["visual_review"]},
            media=[Medium.IMAGE],
        ),
        "p",
    )
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")

    result = Toolbox(ctx, [TOOLS["plan_exploration"]]).call("a", "plan_exploration", plan_arguments(5))

    assert not result.get("is_error"), result
    rows = ctx.ledger.concepts("p", 1)
    assert [(row.letter, row.lever) for row in rows] == [
        ("a", "il nome"),
        ("b", "il gesto"),
        ("c", "la materia"),
        ("d", "le persone"),
        ("e", "la convenzione rovesciata"),
    ]
    specs = [ctx.ledger.spec(row.idea_ticket) for row in rows]
    assert [spec.assignee for spec in specs] == [
        "direction-a",
        "direction-b",
        "direction-c",
        "direction-d",
        "direction-e",
    ]
    assert [(spec.title, spec.workspace, spec.outputs) for spec in specs] == [
        (
            f"Esplorazione {letter.upper()}",
            f"explorations/r1/{letter}",
            ["scheda.json", f"schizzi-{letter}.vectorcraft", f"foglio-{letter}.png", f"schizzo-{letter}.png"],
        )
        for letter in "abcde"
    ]


def test_board_letters_are_stable_and_shuffled_by_project() -> None:
    first = board.assign_letters("merlo", 1, ["a", "b", "c"])
    assert first == board.assign_letters("merlo", 1, ["a", "b", "c"])
    assert sorted(first.values()) == ["X", "Y", "Z"]
    seen = {tuple(board.assign_letters(f"p{n}", 1, ["a", "b", "c"]).values()) for n in range(20)}
    assert len(seen) > 1


def test_board_gives_every_sketch_the_same_space_and_fits_the_limit(tmp_path: Path) -> None:
    small = Image.new("RGB", (612, 792), (255, 255, 255))
    small.paste((0, 0, 0), (290, 380, 320, 410))
    small.save(tmp_path / "piccolo.png")
    output = tmp_path / "tavola.png"
    board.build([(letter, tmp_path / "piccolo.png") for letter in "VWXYZ"], output)
    with Image.open(output) as image:
        assert max(image.size) <= 1600
        gray = image.convert("L")
    cell = gray.crop((30, 40, 510, 520))
    assert cell.point([255] * 128 + [0] * 128).histogram()[255] > 80_000


def test_critic_judges_blind(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0005"] = [
        turn(use("read_file", path="schede.md")),
        turn(use("read_file", path="../../explorations/r1/a/scheda.json")),
        *board_turns(),
    ]
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    requests = transport.requests["T-0005"]
    assert requests[1]["messages"][-1]["content"][0]["is_error"]
    assert requests[2]["messages"][-1]["content"][0]["is_error"]


def test_every_letter_must_be_rated(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptRow(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    box = Toolbox(ctx, [TOOLS["rate_board"]])
    partial = {"ratings": [{"letter": "X", "first_look": "Un merlo", "passes": True}]}
    assert box.call("a", "rate_board", partial)["is_error"]


def test_director_cannot_choose_what_failed_the_first_look(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    for letter, anon in (("a", "X"), ("b", "Y")):
        open_idea(
            ctx.ledger,
            ConceptRow(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    box = Toolbox(ctx, [TOOLS["select_concepts"]])
    assert box.call("a", "select_concepts", {"chosen": ["X"], "reasons": "r"})["is_error"]
    verdicts = settings(tmp_path).layout.ratings(ProjectName("p"), 1)
    verdicts.parent.mkdir(parents=True)
    rated = [
        {"letter": "X", "first_look": "Un tasto", "passes": False},
        {"letter": "Y", "first_look": "Un merlo", "passes": True},
    ]
    verdicts.write_text(json.dumps(rated))
    refused = box.call("b", "select_concepts", {"chosen": ["X", "Y"], "reasons": "r"})
    assert refused["is_error"] and "primo sguardo" in refused["content"]
    assert not box.call("c", "select_concepts", {"chosen": ["Y"], "reasons": "r"}).get("is_error")


def test_nothing_passes_the_first_look_starts_a_new_exploration(tmp_path: Path) -> None:
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    script["T-0001:select"] = [turn(use("select_concepts", chosen=[], reasons="Nessun segno regge"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert "Nessun segno regge" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_client_can_refuse_every_proposal(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", False, "Troppo freddo, voglio calore")
    assert not session.ledger.gates("officina")[0].approved
    assert "calore" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_choice_outside_the_options_is_not_approved(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Prendo la Z", "Z")
    assert not session.ledger.gates("officina")[0].approved
    titles = [session.ledger.spec(row.id).title for row in session.ledger.tickets("officina")]
    assert not any(title.startswith("Rifinitura") for title in titles)


def test_select_refuses_unknown_letters(tmp_path: Path) -> None:
    ctx = context(tmp_path, "design-director")
    open_idea(ctx.ledger, ConceptRow(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X"))
    box = Toolbox(ctx, [TOOLS["select_concepts"]])
    assert box.call("a", "select_concepts", {"chosen": ["Q"], "reasons": "perché sì"})["is_error"]


def test_select_concepts_refuses_more_than_three(tmp_path: Path) -> None:
    """Every letter passed the first look, so only the limit of three stops this choice."""
    ctx = context(tmp_path, "design-director")
    anons = {"a": "W", "b": "X", "c": "Y", "d": "Z"}
    for letter, anon in anons.items():
        open_idea(
            ctx.ledger,
            ConceptRow(project="p", round=1, letter=letter, lever="l", idea_ticket="", anon=anon),
        )
    verdicts = settings(tmp_path).layout.ratings(ProjectName("p"), 1)
    verdicts.parent.mkdir(parents=True)
    passed = [{"letter": anon, "first_look": "Un segno", "passes": True} for anon in anons.values()]
    verdicts.write_text(json.dumps(passed))
    box = Toolbox(ctx, [TOOLS["select_concepts"]])

    result = box.call("a", "select_concepts", {"chosen": list(anons.values()), "reasons": "tutte reggono"})

    assert result["is_error"]
    assert result["content"] == "si sviluppano al massimo 3 idee: sceglierne di più significa non aver scelto"


def test_judge_refuses_a_file_against_itself(tmp_path: Path) -> None:
    """The same file under another spelling is still itself. The file was viewed, so nothing else refuses."""
    ctx = context(tmp_path)
    Image.new("RGB", (60, 60), (20, 20, 20)).save(tmp_path / "segno.png")
    box = Toolbox(ctx, [TOOLS["view_image"], TOOLS["judge"]])
    box.call("a", "view_image", {"path": "segno.png"})

    arguments = {"file": "segno.png", "compare": ["./segno.png"], "why": WHY, "result": "PASS"}
    result = box.call("b", "judge", arguments)

    assert result["is_error"]
    assert result["content"] == "un file non si confronta con se stesso"


def test_export_master_refuses_unknown_options(tmp_path: Path) -> None:
    ctx = context(tmp_path, "identity-designer")
    box = Toolbox(ctx, [TOOLS["export_master"]])
    options = ["--scale", "2", "--plugin", "x.js"]

    result = box.call("a", "export_master", {"master": MASTER, "output": SVG, "options": options})

    assert result["is_error"]
    assert result["content"] == "opzioni non ammesse: ['--plugin']"


def test_a_hidden_image_never_reaches_the_presentation(tmp_path: Path) -> None:
    """A dot-file left in a proposal's applications is never delivered, so no page may show it."""
    folder = tmp_path / "proposals/r1/v"
    applications = folder / "applicazioni-v"
    applications.mkdir(parents=True)
    Image.new("RGB", (300, 300), (30, 60, 200)).save(folder / "proposta-v.png")
    Image.new("RGB", (300, 300), (240, 240, 240)).save(applications / "insegna.png")
    Image.new("RGB", (300, 300), (13, 201, 77)).save(applications / ".zz.png")
    ctx = context(tmp_path, "design-director", "T-0001")
    root = ctx.ledger.open(
        TicketSpec(
            title="Radice",
            request="r",
            type=TicketType.PRODUCTION,
            sender="design-director",
            assignee="design-director",
            outputs=["x.png"],
            checks={"*.png": ["visual_review"]},
            media=[Medium.IMAGE],
        ),
        "p",
    )
    spec = TicketSpec(
        title="Proposta V r1",
        request="Sviluppa la proposta",
        type=TicketType.PROPOSAL,
        sender="design-director",
        assignee="identity-designer",
        outputs=["proposta-v.png", "applicazioni-v/*.png"],
        checks={"*.png": ["visual_review"]},
        media=[Medium.IMAGE],
        parent=root,
        workspace="proposals/r1/v",
    )
    delivered, _ = delivery.expected(spec, folder)
    assert delivered == ["proposta-v.png", "applicazioni-v/insegna.png"]
    ticket = ctx.ledger.open(spec, "p")
    ctx.ledger.apply(
        ticket,
        Action.DELIVER,
        "identity-designer",
        "consegna",
        None,
        {path: sha256(folder / path) for path in delivered},
    )
    open_idea(
        ctx.ledger,
        ConceptRow(project="p", round=1, letter="a", lever="l", idea_ticket="", anon="V", status="proposta"),
    )
    text = {"letter": "V", "title": "T", "idea": "I", "why": "W", "risk": "R"}

    done = Toolbox(ctx, [TOOLS["draft_presentation"]]).call(
        "a", "draft_presentation", {"proposals": [text], "recommended": "V", "reasons": "r"}
    )

    assert not done.get("is_error"), done
    colours = set()
    for page in sorted(tmp_path.glob("presentation/r1/pagina-*.png")):
        with Image.open(page) as image:
            counted = image.convert("RGB").getcolors(presentation.WIDTH * presentation.HEIGHT) or []
            colours |= {colour for _, colour in counted}
    assert (30, 60, 200) in colours  # the delivered mark is shown
    assert (13, 201, 77) not in colours


def test_finisher_cannot_explore(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    spec = TicketSpec(
        title="Costruzione",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="identity-designer",
        outputs=[MASTER],
        checks={"*.vectorcraft": ["master_open"]},
        media=[Medium.VECTOR],
        prompt="finisher",
    )
    ticket = ledger.open(spec, "p")
    index = CommandIndex.load(tmp_path / "index")
    config = settings(tmp_path)
    inputs = config.layout.ops_inputs(ProjectName("p"), "i")
    inputs.mkdir(parents=True)
    sandbox, store = Sandbox(tmp_path, ops=inputs), FileStore(tmp_path / "a")
    ctx = ToolContext("identity-designer", "p", ticket, "i", ledger, sandbox, index, store, settings=config)
    box = Toolbox(ctx)
    refused = box.call("a", "craft_run", {"document": "source/prova.vectorcraft", "steps": DRAW})
    assert refused["is_error"] and "niente file di esplorazione" in refused["content"]
    assert not box.call("b", "craft_run", {"document": MASTER, "steps": DRAW}).get("is_error")


def test_rejected_concept_goes_back_to_exploration(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="Il concetto non regge a piccola scala"))]
    script["T-0001"] = [turn(use("reject_concept", reason="A piccola scala l'idea sparisce del tutto"))]
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    assert "sparisce" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def test_one_failed_explorer_does_not_stop_the_others(tmp_path: Path) -> None:
    script = exploration()
    script["T-0001:plan"] = plan_turn()
    script["T-0002"] = [turn(use("block", reason="Idea impossibile"))]
    script["T-0005"] = board_turns("YZ")
    script["T-0001:select"] = [turn(use("block", reason="prova finita"))]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert sorted(row.anon for row in session.ledger.concepts("officina", 1) if row.anon) == ["Y", "Z"]


def test_interrupted_exploration_resumes_without_repeating_work(tmp_path: Path) -> None:
    config = settings(tmp_path)
    script = to_the_gate()

    class Dies(Router):
        def stream(self, params: dict) -> dict:
            if self.key(params) == "T-0005":
                raise ConnectionError("process killed")
            return super().stream(params)

    dying = Dies(script)
    session = open_session(config, dying)
    with pytest.raises(ConnectionError):
        session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    done = {key: len(value) for key, value in dying.requests.items()}
    again = Router(script)
    second = open_session(config, again)
    second.resume("officina")
    assert second.pending("officina")[0].gate == "concept"
    assert not set(done) & set(again.requests)
    assert len(second.ledger.tickets("officina")) == 7


def test_second_exploration_is_rated_on_its_own_letters(tmp_path: Path) -> None:
    """A second round with fewer levers has letters other than the first's: the critic must see the right
    ones."""
    script = exploration()
    script["T-0005"] = board_turns("XYZ", failing="XYZ")
    script["T-0001:plan"] = [*plan_turn(), *plan_turn(2)]
    script.update(exploration(first=6, count=2))
    script["T-0001:select"] = [
        turn(use("select_concepts", chosen=[], reasons="Nessun segno regge")),
        turn(use("block", reason="prova finita")),
    ]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    work = settings(tmp_path).project_dir(ProjectName("officina")) / "work"
    rated = json.loads((work / "board/r2/reviews/valutazione.json").read_text())
    assert {item["letter"] for item in rated} == {"Y", "Z"}


def test_new_concept_after_a_rejection_gets_its_own_production(tmp_path: Path) -> None:
    """The second finishing ticket starts from the new approved master, not from the first idea's."""
    script = to_the_gate()
    script["T-0008"] = [turn(use("block", reason="Il concetto non regge a piccola scala"))]
    script["T-0001"] = [
        turn(use("reject_concept", reason="A piccola scala l'idea sparisce del tutto")),
        turn(use("block", reason="prova finita")),
    ]
    script["T-0001:plan"] = [*plan_turn(), *plan_turn()]
    script.update(exploration(first=9))
    script["T-0001:select"] = [
        *script["T-0001:select"],
        turn(use("select_concepts", chosen=["Y"], reasons="Si legge da sola")),
    ]
    second = proposal_turns("Y")
    second[1]["content"][0]["input"]["steps"] = [
        {**DRAW[0], "params": {"d": "M10 10 L90 10 L90 90 L10 90 Z"}},
        *DRAW[1:],
    ]
    script["T-0013"] = second
    script["T-0001:present"] = [*script["T-0001:present"], *present_turn("Y", round_=2)]
    session = open_session(settings(tmp_path), Router(script))
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    session.decide("officina", True, "Mi piace la X", "X")
    session.decide("officina", True, "Mi piace la Y", "Y")
    assert session.ledger.spec("T-0014").prompt == "finisher"
    work = settings(tmp_path).project_dir(ProjectName("officina")) / "work"
    assert sha256(work / MASTER) == sha256(work / "proposals/r2/y/proposta-y.vectorcraft")


def proposal(text: str = "Testo", applications: int = 5, tmp: Path | None = None) -> presentation.Proposal:
    assert tmp is not None
    tmp.mkdir(exist_ok=True)
    mark = tmp / "segno.png"
    Image.new("RGB", (400, 300), (20, 20, 20)).save(mark)
    images = []
    for number in range(applications):
        images.append(tmp / f"uso-{number}.png")
        Image.new("RGB", (900, 500), (200, 200, 190)).save(images[-1])
    return presentation.Proposal("V", "Il merlo", text, text, text, mark, tuple(images))


def test_long_texts_flow_on_new_pages_and_nothing_is_lost() -> None:
    words = " ".join(f"parola{number}" for number in range(900))
    columns = presentation.flow(
        [presentation.Block(words, "Perché"), presentation.Block(words, "Limite")], 1100, 790, first=500
    )
    assert len(columns) > 1
    for index, lines in enumerate(columns):
        limit = 500 if index == 0 else 790
        assert all(line.y + int(line.size * presentation.LEADING) <= limit for line in lines)
    written = " ".join(line.text for lines in columns for line in lines)
    assert written.count("parola899") == 2
    assert written.count("parola0 ") == 2


def test_no_line_is_wider_than_its_column() -> None:
    text = "Una parola lunghissima " + "a" * 400 + " e poi il resto del testo\nsu un altro capoverso"
    lines = presentation.wrap(text, 28, 660)
    assert all(presentation.font(28).getlength(line) <= 660 for line in lines)
    assert "".join(lines).count("a" * 300) == 1
    assert lines[-1] == "su un altro capoverso"


def test_merlo3_texts_are_entirely_inside_the_document(tmp_path: Path) -> None:
    """The real case: 541 characters of reasons and a 772 limit ran off the page."""
    long = "Il segno nasce da due cose che ha solo la vostra officina e dal lavoro che la distingue. " * 9
    item = proposal(long, tmp=tmp_path / "file")
    pages = presentation.build([item], "V", long, tmp_path / "pdf")
    assert (tmp_path / "pdf/presentazione.pdf").exists()
    assert len(pages) >= 4
    for page in pages:
        with Image.open(page) as image:
            assert image.size == (presentation.WIDTH, presentation.HEIGHT)
            ink = image.convert("L").point([255] * 200 + [0] * 56)
            assert ink.getbbox()[3] <= presentation.HEIGHT - 20  # type: ignore[index]


def test_a_shorter_draft_leaves_no_old_pages(tmp_path: Path) -> None:
    long = "Testo lungo che continua. " * 400
    first = presentation.build([proposal(long, tmp=tmp_path / "a")], "V", long, tmp_path / "pdf")
    second = presentation.build([proposal("Corto", tmp=tmp_path / "a")], "V", "Corto", tmp_path / "pdf")
    assert len(second) < len(first)
    assert sorted(tmp_path.glob("pdf/pagina-*.png")) == sorted(second)


def test_presentation_cannot_reach_the_client_unseen(tmp_path: Path) -> None:
    """Nobody had looked at merlo3's PDF: the text was cut and nobody noticed."""
    script = to_the_gate()
    views = present_turn("X", "Y")
    script["T-0001:present"] = [
        views[0],
        turn(use("present_concepts")),  # refused: it looked at nothing
        views[1],
        turn(
            use(
                "draft_presentation",
                proposals=views[0]["content"][0]["input"]["proposals"],
                recommended="Y",
                reasons="Ci abbiamo ripensato, questa regge meglio",
            )
        ),
        turn(use("present_concepts")),  # refused: the last page changed
        turn(use("view_image", path="presentation/r1/pagina-7.png")),
        turn(use("present_concepts")),
    ]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    refused = [
        message["content"][0]["content"]
        for message in transport.requests["T-0001:present"][-1]["messages"]
        if message["role"] == "user" and isinstance(message["content"], list)
        if message["content"][0].get("is_error")
    ]
    assert len(refused) == 2
    assert "pagina-1.png" in refused[0]
    assert "pagina-7.png" in refused[1] and "pagina-1.png" not in refused[1]
    assert concept_gate(session, "officina").recommended == "Y"


def test_empty_draft_goes_back_to_exploration_and_survives_a_resume(tmp_path: Path) -> None:
    script = to_the_gate()
    script["T-0001:present"] = [
        turn(
            use(
                "draft_presentation",
                proposals=[],
                recommended=None,
                reasons="Nessuna regge davanti al cliente",
            )
        )
    ]
    script["T-0001:plan"] = [*plan_turn(), turn(use("block", reason="prova finita"))]
    transport = Router(script)
    session = open_session(settings(tmp_path), transport)
    session.start("officina", brief(tmp_path), OUTPUTS, CHECKS, budget=BUDGET)
    assert "Nessuna regge" in transport.requests["T-0001:plan"][1]["messages"][0]["content"]


def write_sketch(path: Path, *boxes: tuple[int, int, int, int], background: str = "white") -> None:
    image = Image.new("RGB", (1200, 800), background)
    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.ellipse(box, fill=(17, 17, 17))
    image.save(path)


def test_board_refuses_nothing_on_a_single_mark(tmp_path: Path) -> None:
    write_sketch(tmp_path / "uno.png", (200, 100, 1000, 700))
    assert board.mark_problem(tmp_path / "uno.png") is None


def test_board_spots_variants_in_the_sketch(tmp_path: Path) -> None:
    write_sketch(
        tmp_path / "tanti.png",
        (20, 300, 240, 520),
        (320, 300, 540, 520),
        (620, 300, 840, 520),
        (920, 300, 1140, 520),
    )
    assert "segni separati" in (board.mark_problem(tmp_path / "tanti.png") or "")


def test_board_ignores_a_light_background(tmp_path: Path) -> None:
    write_sketch(tmp_path / "fondo.png", (500, 300, 700, 500), background="#f4f1ea")
    board.build([("V", tmp_path / "fondo.png")], tmp_path / "tavola.png")
    with Image.open(tmp_path / "tavola.png") as image:
        outside_the_mark = image.convert("RGB").getpixel((65, 145))  # it was beige, inside the frame
    assert outside_the_mark == (255, 255, 255)


def test_explorer_is_warned_once_then_can_insist(tmp_path: Path) -> None:
    """It is an estimate: a real mark in several parts must not stay blocked."""
    ledger = Ledger(tmp_path / "l.sqlite")
    spec = TicketSpec(
        title="Esplorazione A",
        request="Cerca",
        type=TicketType.SKETCH,
        sender="design-director",
        assignee="direction-a",
        outputs=["scheda.json", "schizzo-a.png"],
        checks={"*.png": ["req:forma"]},
        exempt={"scheda.json": "la giudicano critico e direttore"},
        media=[Medium.NONE],
        medium_why="prova senza master",
    )
    concept = ConceptRow(project="p", round=1, letter="a", lever="il nome", idea_ticket="")
    ticket = ledger.open(spec, "p", concept=concept)
    work = tmp_path / "work"
    work.mkdir()
    write_sketch(work / "schizzo-a.png", (20, 300, 240, 520), (920, 300, 1140, 520))
    ctx = ToolContext(
        "direction-a",
        "p",
        ticket,
        "i",
        ledger,
        Sandbox(work),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        settings=settings(tmp_path),
    )
    toolbox = Toolbox(ctx, tools_for("direction-a", spec))
    evidence = {
        "file": "schizzo-a.png",
        "check": "req:forma",
        "result": "PASS",
        "note": "un segno in due parti",
    }
    Toolbox(ctx, [TOOLS["record_requirement"]]).call("e1", "record_requirement", evidence)
    first = toolbox.call("s1", "submit_concept", card("Due parti"))
    assert first.get("is_error")
    assert "segni separati" in first["content"]
    second = toolbox.call("s2", "submit_concept", card("Due parti"))
    assert not second.get("is_error")
    assert ledger.status(ticket)[0] is Status.DELIVERED
