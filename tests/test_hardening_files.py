"""Defects found by rereading the system before M2: the agent tools reach the work folder only through the no-
follow helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from agency.contracts.concept import ConceptCard
from agency.contracts.ledger import (
    ConceptEntry,
)
from agency.contracts.project import ProjectName
from agency.contracts.ticket import Medium, TicketType
from agency.qa import evidence
from agency.toolkit.base import ToolContext
from agency.toolkit.review import _seen_proof
from agency.workshop.craft import CommandIndex
from agency.workshop.files import OutsidePerimeter, is_file_under
from agency.workshop.sandbox import Sandbox
from support.concepts import open_idea
from support.hardening import board_critic, context, director, rating, spec, use
from support.hardening_fixtures import own_data_folder, sandbox_scope_ready  # noqa: F401 (autouse fixtures)
from support.rules import RULES
from support.settings import settings

# The agent tools reach the work folder only through the no-follow helpers (2.F9-2.F11), the critic's
# ratings live where only the harness writes (2.F24) and the pages to check come from the draft (2.F26)

SECRET = "contenuto riservato del cliente"


WHY = "Il segno tondo regge alla dimensione d'uso, quello a doppio filo si impasta e perde la figura."


WHERE = pytest.mark.parametrize("where", ["outside", "inside"])


def host_folder(tmp_path: Path, where: str, ctx: ToolContext) -> Path:
    """A folder with a file the work must never read or change: outside the work folder, or in it (a link
    to a neighbour's files stays inside the perimeter, so `inside()` lets it through)."""
    host = tmp_path / "host-folder" if where == "outside" else ctx.work / "altrove"
    host.mkdir(parents=True)
    (host / "segreto.txt").write_text(SECRET, encoding="utf-8")
    return host


def untouched(host: Path) -> bool:
    names = sorted(path.name for path in host.iterdir())
    return names == ["segreto.txt"] and (host / "segreto.txt").read_text(encoding="utf-8") == SECRET


PLAN: dict[str, Any] = {
    "levers": [{"lever": "il nome"}, {"lever": "il gesto"}],
    "assets": ["forno"],
    "excluded": ["la spiga", "il cerchio", "il fumo"],
    "applications": [{"name": "insegna", "size": "16 mm"}, {"name": "scatola", "size": "4 cm"}],
}


@WHERE
def test_plan_exploration_never_writes_the_plan_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")
    (ctx.work / "explorations").symlink_to(host, target_is_directory=True)

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_plan_exploration_never_makes_an_explorer_folder_through_a_planted_link(
    tmp_path: Path, where: str
) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").write_text("il brief", encoding="utf-8")
    (ctx.work / "explorations/r1").mkdir(parents=True)
    (ctx.work / "explorations/r1/a").symlink_to(host, target_is_directory=True)

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_plan_exploration_never_copies_a_linked_brief_to_an_explorer(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "brief.md").symlink_to(host / "segreto.txt")

    result = use(ctx, "plan_exploration", **PLAN)

    assert result.get("is_error"), result
    assert not list(ctx.work.glob("explorations/r1/*/brief.md"))
    assert untouched(host)


CARD = ConceptCard(
    concept="Il forno come casa", client_fact="f", why_not_obvious="w", drawing="d", substitution="s"
)


def sketcher(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "direction-a", "T-0")
    ctx.settings = settings(tmp_path)
    sketch = spec(
        type=TicketType.SKETCH,
        assignee="direction-a",
        outputs=["scheda.json", "schizzo-a.png"],
        checks={"*.png": ["visual_review"]},
        exempt={"scheda.json": "la scheda la giudicano critico e direttore"},
        media=[Medium.VECTOR],
    )
    ctx.ticket_id = ctx.ledger.open(sketch, "p")
    return ctx


@WHERE
def test_submit_concept_never_writes_the_card_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = sketcher(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "scheda.json").symlink_to(host / "segreto.txt")

    use(ctx, "submit_concept", **CARD.model_dump())

    assert untouched(host)


def selector(critic: ToolContext) -> ToolContext:
    """The director who chooses: same project and ledger, the work folder above the board."""
    ctx = ToolContext(
        "design-director",
        "p",
        "T-1",
        "j",
        critic.ledger,
        Sandbox(critic.work.parent.parent),
        CommandIndex([]),
        critic.artifacts,
        settings=critic.settings,
        rules=RULES,
    )
    return ctx


@WHERE
def test_rate_board_never_writes_the_rating_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = board_critic(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "reviews").symlink_to(host, target_is_directory=True)

    result = use(ctx, "rate_board", ratings=rating("X", "Y", passing="X"))

    assert result.get("is_error"), result
    assert untouched(host)


def test_select_concepts_ignores_a_rating_forged_in_the_work_folder(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    chooser = selector(critic)
    forged = json.dumps(rating("X", "Y", passing="XY"))
    assert not use(critic, "write_file", path="reviews/valutazione.json", content=forged).get("is_error")

    result = use(chooser, "select_concepts", chosen=["X"], reasons="r")

    assert result.get("is_error"), result
    assert "la tavola del giro 1 non è stata valutata con rate_board" in result["content"]


def test_select_concepts_lets_through_only_what_rate_board_recorded(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    chooser = selector(critic)
    assert not use(critic, "rate_board", ratings=rating("X", "Y", passing="X")).get("is_error")
    forged = json.dumps(rating("X", "Y", passing="XY"))
    assert not use(critic, "write_file", path="reviews/valutazione.json", content=forged).get("is_error")

    refused = use(chooser, "select_concepts", chosen=["Y"], reasons="r")
    chosen = use(chooser, "select_concepts", chosen=["X"], reasons="r")

    assert refused.get("is_error") and "primo sguardo" in refused["content"]
    assert not chosen.get("is_error"), chosen


def test_rate_board_still_writes_the_ticket_output_and_the_harness_copy(tmp_path: Path) -> None:
    critic = board_critic(tmp_path)
    ratings = rating("X", "Y", passing="X")

    assert not use(critic, "rate_board", ratings=ratings).get("is_error")

    assert json.loads((critic.work / "reviews/valutazione.json").read_text(encoding="utf-8")) == ratings
    assert critic.settings is not None
    kept = critic.settings.layout.ratings(ProjectName("p"), 1)
    assert kept == critic.settings.layout.root / "ops" / "p" / "ratings-r1.json"
    assert json.loads(kept.read_text(encoding="utf-8")) == ratings


def proposal_ready(tmp_path: Path) -> ToolContext:
    ctx = context(tmp_path, "design-director", "T-0")
    ctx.settings = settings(tmp_path)
    open_idea(
        ctx.ledger,
        ConceptEntry(
            project="p", round=1, letter="a", lever="l", idea_ticket="", anon="X", status="proposta"
        ),
    )
    folder = ctx.work / "proposals/r1/x"
    folder.mkdir(parents=True)
    Image.new("RGB", (300, 200), (20, 20, 20)).save(folder / "proposta-x.png")
    return ctx


DRAFT: dict[str, Any] = {
    "proposals": [{"letter": "X", "title": "T", "idea": "I", "why": "W", "risk": "R"}],
    "recommended": "X",
    "reasons": "r",
}


@WHERE
def test_draft_presentation_never_writes_the_pages_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = proposal_ready(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "presentation").symlink_to(host, target_is_directory=True)

    result = use(ctx, "draft_presentation", **DRAFT)

    assert result.get("is_error"), result
    assert untouched(host)


@WHERE
def test_draft_presentation_never_writes_the_texts_through_a_planted_link(tmp_path: Path, where: str) -> None:
    ctx = proposal_ready(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "presentation/r1").mkdir(parents=True)
    (ctx.work / "presentation/r1/testi.json").symlink_to(host / "segreto.txt")

    use(ctx, "draft_presentation", **DRAFT)

    assert untouched(host)


def drafted(tmp_path: Path) -> tuple[ToolContext, list[str]]:
    ctx = proposal_ready(tmp_path)
    done = use(ctx, "draft_presentation", **DRAFT)
    assert not done.get("is_error"), done
    return ctx, json.loads(done["content"])["pagine"]


def view_all(ctx: ToolContext, pages: list[str]) -> None:
    for page in pages:
        assert not use(ctx, "view_image", path=page).get("is_error")


@WHERE
def test_present_concepts_never_sends_a_linked_draft(tmp_path: Path, where: str) -> None:
    ctx, pages = drafted(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    view_all(ctx, pages)
    (ctx.work / "presentation/r1/testi.json").unlink()
    (ctx.work / "presentation/r1/testi.json").symlink_to(host / "segreto.txt")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert SECRET not in str(result)
    assert ctx.finished is None


def test_present_concepts_checks_the_pages_of_the_draft_and_only_those(tmp_path: Path) -> None:
    ctx, pages = drafted(tmp_path)
    Image.new("RGB", (50, 50), (200, 0, 0)).save(ctx.work / "presentation/r1/pagina-99.png")
    view_all(ctx, pages)

    result = use(ctx, "present_concepts")

    assert not result.get("is_error"), result
    assert ctx.finished is not None


def test_present_concepts_refuses_a_page_of_the_draft_that_is_gone(tmp_path: Path) -> None:
    ctx, pages = drafted(tmp_path)
    view_all(ctx, pages)
    (ctx.work / pages[-1]).unlink()

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert pages[-1] in result["content"]
    assert ctx.finished is None


@WHERE
def test_present_concepts_refuses_a_page_that_became_a_link(tmp_path: Path, where: str) -> None:
    ctx, pages = drafted(tmp_path)
    view_all(ctx, pages)
    page, host = ctx.work / pages[0], host_folder(tmp_path, where, ctx)
    (host / "pagina.png").write_bytes(page.read_bytes())
    page.unlink()
    page.symlink_to(host / "pagina.png")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert ctx.finished is None


def seen_image(tmp_path: Path, where: str) -> ToolContext:
    """An image the agent has viewed, then swapped for a link to a host file with the same bytes."""
    ctx = context(tmp_path, "critic")
    host = host_folder(tmp_path, where, ctx)
    image = ctx.work / "segno.png"
    Image.new("RGB", (60, 60), (20, 20, 20)).save(image)
    assert not use(ctx, "view_image", path="segno.png").get("is_error")
    (host / "fuori.png").write_bytes(image.read_bytes())
    image.unlink()
    image.symlink_to(host / "fuori.png")
    return ctx


@WHERE
def test_a_proof_that_became_a_link_is_not_the_version_that_was_seen(tmp_path: Path, where: str) -> None:
    """`evidence.record` refuses a link too, but the proof is picked first: its hash is not a target's."""
    ctx = seen_image(tmp_path, where)

    with pytest.raises(OutsidePerimeter):
        _seen_proof(ctx, "segno.png")


@WHERE
def test_judge_does_not_compare_against_a_link(tmp_path: Path, where: str) -> None:
    ctx = context(tmp_path, "critic")
    host = host_folder(tmp_path, where, ctx)
    Image.new("RGB", (60, 60), (20, 20, 20)).save(ctx.work / "segno.png")
    Image.new("RGB", (60, 60), (200, 20, 20)).save(host / "altro.png")
    (ctx.work / "altro.png").symlink_to(host / "altro.png")
    assert not use(ctx, "view_image", path="segno.png").get("is_error")

    result = use(ctx, "judge", file="segno.png", compare=["altro.png"], why=WHY, result="PASS")

    assert result.get("is_error"), result
    assert "inesistenti" in result["content"]


@WHERE
def test_open_ticket_does_not_take_a_link_as_an_input(tmp_path: Path, where: str) -> None:
    ctx = director(tmp_path)
    host = host_folder(tmp_path, where, ctx)
    (ctx.work / "riferimento.txt").symlink_to(host / "segreto.txt")

    result = use(
        ctx,
        "open_ticket",
        title="Segno",
        request="Disegna",
        type="produzione",
        assignee="identity-designer",
        outputs=["a.md"],
        checks={"*.md": ["req:testo"]},
        media=["nessuno"],
        medium_why="solo testo, nessun mezzo visivo",
        inputs=["riferimento.txt"],
    )

    assert result.get("is_error"), result
    assert "input inesistenti" in result["content"]


@WHERE
def test_deliver_never_hashes_an_output_that_is_a_link(tmp_path: Path, where: str) -> None:
    ctx = context(tmp_path, "identity-designer")
    host = host_folder(tmp_path, where, ctx)
    ctx.ticket_id = ctx.ledger.open(spec(), "p")
    (ctx.work / "a.md").write_text("nota", encoding="utf-8")
    evidence.record(
        ctx.ledger,
        ctx.work,
        "p",
        "a.md",
        "req:testo",
        "PASS",
        ctx.actor,
        ctx.ticket_id,
        note="ok",
        rules=RULES,
    )
    (ctx.work / "a.md").unlink()
    (ctx.work / "a.md").symlink_to(host / "segreto.txt")

    result = use(ctx, "deliver", note="Consegnato.", verdict=None)

    assert result.get("is_error"), result
    assert ctx.finished is None


def test_is_file_under_is_true_only_for_a_regular_file_that_is_not_a_link(tmp_path: Path) -> None:
    work, host = tmp_path / "work", host_folder(tmp_path, "outside", context(tmp_path))
    (work / "dentro").mkdir()
    (work / "dentro/a.txt").write_text("a", encoding="utf-8")
    (work / "link.txt").symlink_to(work / "dentro/a.txt")
    (work / "cartella-link").symlink_to(host, target_is_directory=True)
    os.mkfifo(work / "tubo")

    assert is_file_under(work, "dentro/a.txt")
    assert not is_file_under(work, "dentro")  # a folder
    assert not is_file_under(work, "link.txt")  # a link, even to a file inside
    assert not is_file_under(work, "cartella-link/segreto.txt")  # a link on the way
    assert not is_file_under(work, "tubo")  # not a regular file, and it does not block
    assert not is_file_under(work, "manca.txt")
    for outside in ("dentro/../dentro/a.txt", "/etc/passwd", ""):
        with pytest.raises(OutsidePerimeter):
            is_file_under(work, outside)


def test_judge_refuses_a_file_compared_with_itself_under_another_spelling(tmp_path: Path) -> None:
    ctx = context(tmp_path, "critic")
    Image.new("RGB", (60, 60), (20, 20, 20)).save(ctx.work / "segno.png")
    assert not use(ctx, "view_image", path="segno.png").get("is_error")

    result = use(ctx, "judge", file="segno.png", compare=["./segno.png"], why=WHY, result="PASS")

    assert result.get("is_error"), result
    assert "con se stesso" in result["content"]


def test_present_concepts_refuses_a_draft_nobody_made(tmp_path: Path) -> None:
    ctx = proposal_ready(tmp_path)
    (ctx.work / "presentation/r1").mkdir(parents=True)
    Image.new("RGB", (50, 50), (200, 0, 0)).save(ctx.work / "presentation/r1/pagina-1.png")
    (ctx.work / "presentation/r1/testi.json").write_text(json.dumps({"planted": True}), encoding="utf-8")

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert "draft_presentation" in result["content"]
    assert ctx.finished is None


def test_present_concepts_checks_the_pages_of_the_latest_draft(tmp_path: Path) -> None:
    ctx, first = drafted(tmp_path)
    two = {**DRAFT, "proposals": [*DRAFT["proposals"], {**DRAFT["proposals"][0], "letter": "Y"}]}
    open_idea(
        ctx.ledger,
        ConceptEntry(
            project="p", round=1, letter="b", lever="l", idea_ticket="", anon="Y", status="proposta"
        ),
    )
    (ctx.work / "proposals/r1/y").mkdir()
    Image.new("RGB", (300, 200), (20, 20, 20)).save(ctx.work / "proposals/r1/y/proposta-y.png")
    second = json.loads(use(ctx, "draft_presentation", **two)["content"])["pagine"]
    assert len(second) > len(first)
    view_all(ctx, first)

    result = use(ctx, "present_concepts")

    assert result.get("is_error"), result
    assert ctx.finished is None
