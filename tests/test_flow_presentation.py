"""The presentation with real Craft and recorded answers: the pages, the draft and the concept gate."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from agency.agents.toolbox import TOOLS, Toolbox
from agency.contracts.gate import ConceptGate
from agency.contracts.ledger import ConceptEntry
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Action, Medium, Status, TicketSpec, TicketType
from agency.process.session import open_session
from agency.qa import delivery
from agency.studio.presentation import document as presentation
from agency.workshop.files import sha256
from support.concepts import open_idea
from support.scripted import turn
from support.settings import settings
from support.sketch import (
    BUDGET,
    CHECKS,
    OUTPUTS,
    Router,
    brief,
    concept_gate,
    context,
    full_script,
    plan_turn,
    present_turn,
    proposal,
    to_the_gate,
    use,
)

pytestmark = pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="serve VectorCraft")


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
        ConceptEntry(
            project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"
        ),
    )
    open_idea(
        ctx.ledger,
        ConceptEntry(project="p", round=1, letter="b", lever="l", idea_ticket="", anon="Y", status="schizzo"),
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
        ConceptEntry(
            project="p", round=1, letter="a", lever="l", idea_ticket="", anon="V", status="proposta"
        ),
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
