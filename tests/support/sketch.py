"""The scripted studio the slice flow tests share: the turns of each phase, the routed transport and the
brief."""

from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from pathlib import Path

from PIL import Image

from agency.artifacts import FileStore
from agency.contracts.gate import ConceptGate
from agency.ledger import Ledger
from agency.process.session import Session
from agency.studio.presentation import document as presentation
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Sandbox
from support.rules import RULES
from support.scripted import turn
from support.settings import settings

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
        rules=RULES,
    )


def concept_gate(session: Session, project: str) -> ConceptGate:
    (gate,) = session.pending(project)
    assert isinstance(gate, ConceptGate)
    return gate


def options(session: Session, project: str) -> list[str]:
    return concept_gate(session, project).options


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
