"""Il giudizio alla cieca di una persona, legato allo sha256 del file giudicato (M1.6, punto 5)."""

from __future__ import annotations

import hashlib
import os
import random
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from agency import cli
from agency.artifacts import FileStore
from agency.config import Settings
from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.evaluation import blind
from agency.insights.views import ProjectReport
from agency.ledger import Ledger
from agency.telemetry import report
from drawings import FakeVectorcraft, red_pixels, svg


def rating(letter: str, level: Level = Level.GOOD, specific: bool = True, why: str = "Si legge") -> Rating:
    return Rating(letter=letter, level=level, specific=specific, why=why)


def scripted(answers: list[str]) -> Callable[[str], str]:
    pending = list(answers)
    return lambda _prompt: pending.pop(0)


# Le regole del giudizio


def test_comparison_needs_the_best_among_its_letters() -> None:
    with pytest.raises(ValidationError, match="migliore"):
        Judgment(judge="andrea", ratings=[rating("A"), rating("B")])
    with pytest.raises(ValidationError, match="migliore"):
        Judgment(judge="andrea", ratings=[rating("A"), rating("B")], best="C")
    assert Judgment(judge="andrea", ratings=[rating("A"), rating("B")], best="B").best == "B"


def test_the_best_cannot_have_a_lower_level_than_another_letter() -> None:
    """Un eccellente non perde da un buono: altrimenti il giudizio non dice quale segno vince."""
    with pytest.raises(ValidationError, match="livello più alto è eccellente"):
        Judgment(judge="andrea", ratings=[rating("A"), rating("B", Level.EXCELLENT)], best="A")
    tied = [rating("A", Level.EXCELLENT), rating("B", Level.EXCELLENT), rating("C")]
    assert {Judgment(judge="andrea", ratings=tied, best=letter).best for letter in "AB"} == {"A", "B"}


def test_single_file_has_no_best() -> None:
    with pytest.raises(ValidationError, match="un solo file"):
        Judgment(judge="andrea", ratings=[rating("A")], best="A")
    assert Judgment(judge="andrea", ratings=[rating("A")]).best is None


def test_every_letter_is_rated_once() -> None:
    with pytest.raises(ValidationError, match="più di un voto"):
        Judgment(judge="andrea", ratings=[rating("A"), rating("A")], best="A")


@pytest.mark.parametrize("why", ["", "   "])
def test_a_rating_needs_its_reason(why: str) -> None:
    with pytest.raises(ValidationError):
        rating("A", why=why)


def test_judgment_needs_someone_who_gives_it() -> None:
    with pytest.raises(ValidationError):
        Judgment(judge=" ", ratings=[rating("A")])


# Le lettere


def files(tmp_path: Path, contents: dict[str, str]) -> list[Path]:
    paths = []
    for name, body in contents.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    return paths


# Le tele dei due segno.svg reali: 98 × 118,5 px e 800 × 600 px, con il disegno al 91% e al 76%.
MERLO = svg((98, 118.5), (6, 6, 86, 108))
MERLO3 = svg((800, 600), (99, 115, 609, 355))


def two_projects(tmp_path: Path) -> list[Path]:
    return files(
        tmp_path,
        {"projects/merlo/work/exports/segno.svg": MERLO, "projects/merlo3/work/exports/segno.svg": MERLO3},
    )


def test_candidates_know_project_file_and_hash(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    assert [candidate.judged for candidate in found] == [
        Judged(project=project, file="exports/segno.svg", sha256=hashlib.sha256(body.encode()).hexdigest())
        for project, body in (("merlo", MERLO), ("merlo3", MERLO3))
    ]


def test_file_outside_the_projects_keeps_its_whole_path(tmp_path: Path) -> None:
    (outside,) = files(tmp_path, {"cli/segno.svg": "<svg>cli</svg>"})
    (candidate,) = blind.candidates([outside], tmp_path / "projects")
    assert (candidate.judged.project, candidate.judged.file) == ("", str(outside.resolve()))


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ({"a/segno.svg": "<svg/>", "b/segno.png": "png"}, "tipi diversi"),
        ({"a/segno.svg": "<svg/>", "b/segno.svg": "<svg/>"}, "identici"),
    ],
)
def test_unfair_comparisons_are_refused(tmp_path: Path, contents: dict[str, str], message: str) -> None:
    with pytest.raises(blind.CannotCompare, match=message):
        blind.candidates(files(tmp_path, contents), tmp_path / "projects")


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(blind.CannotCompare, match="non trovato"):
        blind.candidates([tmp_path / "manca.svg"], tmp_path / "projects")


def test_letters_follow_the_draw_not_the_order_of_the_arguments(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    first_is_a = {blind.assign(found, random.Random(seed))["A"] == found[0] for seed in range(20)}
    assert first_is_a == {True, False}
    assert list(blind.assign(found, random.Random(0))) == ["A", "B"]


def test_blind_copies_have_only_the_letter_in_their_name(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    assigned = blind.assign(found, random.Random(1))
    copies = blind.lay_out(assigned, tmp_path / "blind" / "s")
    assert [copy.name for copy in copies] == ["A.svg", "B.svg"]
    for copy in copies:
        assert copy.read_bytes() == assigned[copy.stem].path.read_bytes()


def test_blind_copies_do_not_keep_the_date_of_the_original(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    for candidate in found:
        os.utime(candidate.path, (946684800, 946684800))  # 2000-01-01
    copies = blind.lay_out(blind.assign(found, random.Random(1)), tmp_path / "blind" / "s")
    assert all(copy.stat().st_mtime > 946684800 for copy in copies)


# Le domande


def test_interview_asks_level_substitution_and_reason_for_each_letter_then_the_best() -> None:
    answers = ["buono", "no", "Si legge da lontano", "Eccellente", "sì", "Bello ma generico", "b"]
    judgment = blind.interview(["A", "B"], scripted(answers), "andrea")
    assert judgment == Judgment(
        judge="andrea",
        ratings=[
            Rating(letter="A", level=Level.GOOD, specific=True, why="Si legge da lontano"),
            Rating(letter="B", level=Level.EXCELLENT, specific=False, why="Bello ma generico"),
        ],
        best="B",
    )


def test_interview_asks_again_until_the_answer_is_one_of_the_options() -> None:
    answers = ["ottimo", "buono", "forse", "si", "  ", "Regge", "eccellente", "no", "Unico", "C", "b"]
    judgment = blind.interview(["A", "B"], scripted(answers), "andrea")
    assert judgment.ratings == [
        Rating(letter="A", level=Level.GOOD, specific=False, why="Regge"),
        Rating(letter="B", level=Level.EXCELLENT, specific=True, why="Unico"),
    ]
    assert judgment.best == "B"


def test_a_best_below_the_highest_level_is_explained_and_asked_again() -> None:
    """La prova generale del punto 16: eccellente A, ordinario B, e B scelto per sbaglio."""
    answers = ["eccellente", "no", "Unico", "ordinario", "si", "Generico", "b", "a"]
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return answers.pop(0)

    judgment = blind.interview(["A", "B"], ask, "andrea")

    assert judgment.best == "A"
    assert prompts[-2] == "Il migliore tra A, B: "
    assert prompts[-1] == (
        "B è ordinario, e il livello più alto è eccellente (A): il migliore è tra questi. "
        "Per cambiare un livello interrompi con Ctrl-C, e non si registra nulla.\n"
        "Il migliore tra A, B: "
    )


def test_single_file_interview_does_not_ask_for_the_best() -> None:
    judgment = blind.interview(["A"], scripted(["ordinario", "no", "Corretto e basta"]), "andrea")
    assert judgment.best is None


# Il registro


def judged(project: str, body: str) -> Judged:
    return Judged(project=project, file="exports/segno.svg", sha256=hashlib.sha256(body.encode()).hexdigest())


def comparison() -> tuple[Judgment, dict[str, Judged]]:
    judgment = Judgment(
        judge="andrea",
        ratings=[rating("A", Level.ORDINARY, why="Ovvio"), rating("B", Level.EXCELLENT, why="Unico")],
        best="B",
    )
    return judgment, {"A": judged("merlo", "uno"), "B": judged("merlo3", "due")}


def test_a_comparison_is_recorded_one_row_per_file(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    judgment, origins = comparison()

    ledger.record_judgment("s1", judgment, origins)

    (row,) = ledger.judgments("merlo3")
    assert (row.comparison, row.judge, row.letter, row.project, row.file) == (
        "s1",
        "andrea",
        "B",
        "merlo3",
        "exports/segno.svg",
    )
    assert (row.sha256, row.level, row.specific, row.best, row.why) == (
        origins["B"].sha256,
        "eccellente",
        True,
        True,
        "Unico",
    )
    assert [r.letter for r in ledger.comparison("s1")] == ["A", "B"]


def test_every_letter_needs_its_file(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    judgment, origins = comparison()
    with pytest.raises(ValueError, match="letters"):
        ledger.record_judgment("s1", judgment, {"A": origins["A"]})
    assert ledger.comparison("s1") == []


@pytest.mark.parametrize("statement", ["UPDATE judgments SET level = 'eccellente'", "DELETE FROM judgments"])
def test_judgments_are_append_only(tmp_path: Path, statement: str) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_judgment("s1", *comparison())
    with ledger.engine.begin() as connection, pytest.raises(Exception, match="solo in aggiunta"):
        connection.exec_driver_sql(statement)


def test_report_of_a_project_shows_its_judgments(
    tmp_path: Path, report_of: Callable[[Path, str], ProjectReport]
) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_judgment("s1", *comparison())
    text = report.render(report_of(tmp_path / "l.sqlite", "merlo3"))
    assert "Giudizi alla cieca:" in text
    assert "exports/segno.svg [B] eccellente, specifico, il migliore di 2" in text


# Il comando


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_board_renderer", FakeVectorcraft)  # la tavola senza dipendere dalla macchina
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    Ledger(settings.ledger_path)  # `judge` needs a registry to exist
    return settings


@pytest.fixture
def unfaked_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Like `studio`, but the board is drawn by the real renderer."""
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    Ledger(settings.ledger_path)  # `judge` needs a registry to exist
    return settings


def answer(monkeypatch: pytest.MonkeyPatch, answers: list[str], seen: list[list[str]]) -> None:
    """Risponde come farebbe Andrea, e annota quali file vedeva nella cartella anonima mentre rispondeva."""
    pending = list(answers)

    def fake_input(prompt: str) -> str:
        folders = list(Path("data/blind").glob("*"))
        seen.append(sorted(path.name for folder in folders for path in folder.iterdir()))
        if not pending:
            raise EOFError
        return pending.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)


def test_judge_records_blind_then_reveals_and_removes_the_copies(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = two_projects(Path.cwd())
    seen: list[list[str]] = []
    answer(monkeypatch, ["buono", "no", "Regge", "ordinario", "si", "Generico", "A"], seen)

    assert cli.main(["judge", *map(str, paths), "--judge", "andrea"]) == 0

    out = capsys.readouterr().out
    assert seen[0] == ["A.svg", "B.svg", "tavola.png"]
    assert "tavola.png  i disegni alla stessa misura" in out
    assert "merlo" not in out.split("Registrati")[0]
    assert "Registrati 2 giudizi di andrea" in out
    ledger = Ledger(studio.ledger_path)
    rows = ledger.judgments("merlo") + ledger.judgments("merlo3")
    assert sorted((row.level, row.best) for row in rows) == [("buono", True), ("ordinario", False)]
    best = next(row for row in rows if row.best)
    assert f"A buono, specifico, il migliore: exports/segno.svg di {best.project}" in out
    assert list(Path("data/blind").iterdir()) == []


def test_judged_files_are_kept_under_their_hash(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = two_projects(Path.cwd())
    answer(monkeypatch, ["buono", "no", "Regge", "ordinario", "si", "Generico", "A"], [])
    assert cli.main(["judge", *map(str, paths), "--judge", "andrea"]) == 0
    for path in paths:  # il file nel progetto può cambiare: la versione giudicata resta
        path.write_text("sovrascritto", encoding="utf-8")

    ledger, store = Ledger(studio.ledger_path), FileStore(studio.artifacts_dir)
    for project, original in (("merlo", MERLO), ("merlo3", MERLO3)):
        (judged,) = ledger.judgments(project)
        with store.open(judged.sha256) as handle:
            assert handle.read() == original.encode()
        (row,) = ledger.artifacts(project)
        assert (row.sha256, row.origin, row.path, row.ticket_id) == (
            judged.sha256,
            "giudizio",
            judged.file,
            "",
        )


def test_a_blind_copy_changed_during_the_judgment_records_nothing(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = two_projects(Path.cwd())
    pending = ["buono", "no", "Regge", "ordinario", "si", "Generico", "A"]

    def tampering_input(_prompt: str) -> str:
        if len(pending) == 1:  # mentre si sceglie il migliore, qualcuno cambia una copia
            (copy,) = Path("data/blind").glob("*/A.svg")
            copy.write_text("<svg>altro</svg>", encoding="utf-8")
        return pending.pop(0)

    monkeypatch.setattr("builtins.input", tampering_input)

    assert cli.main(["judge", *map(str, paths)]) == 1

    assert "cambiat" in capsys.readouterr().out
    ledger = Ledger(studio.ledger_path)
    assert ledger.judgments("merlo") + ledger.judgments("merlo3") == []
    assert ledger.artifacts("merlo") + ledger.artifacts("merlo3") == []


def test_a_file_changed_while_it_is_copied_is_refused(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    found[0].path.write_text("<svg>cambiato</svg>", encoding="utf-8")
    with pytest.raises(blind.CannotCompare, match="cambiato"):
        blind.lay_out(blind.assign(found, random.Random(1)), tmp_path / "blind" / "s")


def test_interrupted_judgment_records_nothing_and_leaves_no_copies(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = two_projects(Path.cwd())
    answer(monkeypatch, ["buono"], [])

    assert cli.main(["judge", *map(str, paths)]) == 1

    assert "nulla registrato" in capsys.readouterr().out
    ledger = Ledger(studio.ledger_path)
    assert ledger.judgments("merlo") == [] and ledger.judgments("merlo3") == []
    assert ledger.artifacts("merlo") == [] and not studio.artifacts_dir.exists()
    assert list(Path("data/blind").iterdir()) == []


def test_judge_refuses_an_unfair_comparison_before_showing_anything(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = files(Path.cwd(), {"projects/a/work/segno.svg": "<svg/>", "projects/b/work/segno.png": "png"})
    seen: list[list[str]] = []
    answer(monkeypatch, [], seen)

    assert cli.main(["judge", *map(str, paths)]) == 1

    assert "tipi diversi" in capsys.readouterr().out
    assert seen == []
    assert not Path("data/blind").exists()


def test_a_file_that_cannot_be_drawn_is_refused_before_any_question(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un disegno vuoto non si mette alla pari con un altro: si rifiuta, e la cartella anonima se ne va."""
    paths = files(
        Path.cwd(),
        {
            "projects/merlo/work/exports/segno.svg": MERLO,
            "projects/vuoto/work/exports/segno.svg": svg((100, 100), (10, 10, 0, 0)),
        },
    )
    seen: list[list[str]] = []
    answer(monkeypatch, [], seen)

    assert cli.main(["judge", *map(str, paths)]) == 1

    out = capsys.readouterr().out
    assert "non ha niente di disegnato. Nulla registrato" in out
    assert "vuoto" not in out  # il rifiuto dice la lettera, non il progetto
    assert seen == []
    assert Ledger(studio.ledger_path).judgments("merlo") == []
    assert list(Path("data/blind").iterdir()) == []


def test_a_type_without_a_board_is_judged_as_it_is_and_says_so(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = files(
        Path.cwd(),
        {"projects/merlo/work/tavola.pdf": "%PDF-1.7 a", "projects/merlo3/work/tavola.pdf": "%PDF-1.7 b"},
    )
    seen: list[list[str]] = []
    answer(monkeypatch, ["buono", "no", "Regge", "ordinario", "si", "Generico", "A"], seen)

    assert cli.main(["judge", *map(str, paths)]) == 0

    assert seen[0] == ["A.pdf", "B.pdf"]
    assert "Per i file .pdf non c'è una tavola" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("vectorcraft-cli") is None, reason="manca vectorcraft-cli")
def test_judge_board_cannot_draw_host_files(
    unfaked_studio: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "hidden/secret.png"
    secret.parent.mkdir()
    Image.new("RGB", (80, 80), (200, 0, 0)).save(secret)
    probe = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        '<rect x="10" y="10" width="80" height="80" fill="#111113"/>'
        f'<image href="{secret}" x="100" y="100" width="80" height="80"/></svg>'
    )
    paths = files(tmp_path, {"cli/probe.svg": probe, "cli/plain.svg": MERLO})
    reds: list[int] = []

    def look(prompt: str) -> str:
        (board_png,) = Path("data/blind").glob("*/tavola.png")
        with Image.open(board_png) as opened:
            reds.append(red_pixels(opened))
        raise EOFError

    monkeypatch.setattr("builtins.input", look)

    assert cli.main(["judge", *map(str, paths), "--judge", "andrea"]) == 1

    assert reds == [0]


def linked_work(tmp_path: Path, kind: str) -> tuple[list[Path], Path]:
    """Two projects' files, the first one reached through a link a sandbox left in its work folder."""
    host = tmp_path / "host"
    host.mkdir()
    (host / "segno.svg").write_text(MERLO, encoding="utf-8")
    other = files(tmp_path, {"projects/merlo3/work/exports/segno.svg": MERLO3})[0]
    exports = tmp_path / "projects/merlo/work/exports"
    exports.parent.mkdir(parents=True)
    if kind == "file":
        exports.mkdir()
        (exports / "segno.svg").symlink_to(host / "segno.svg")
    else:
        exports.symlink_to(host, target_is_directory=True)
    return [exports / "segno.svg", other], host


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_a_link_in_a_projects_work_folder_is_not_read_or_hashed(tmp_path: Path, kind: str) -> None:
    paths, _ = linked_work(tmp_path, kind)
    with pytest.raises(blind.CannotCompare, match="fuori dalla cartella del lavoro"):
        blind.candidates(paths, tmp_path / "projects")


def test_a_file_swapped_for_a_link_before_the_copy_is_not_copied(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    target = found[0].path
    host = tmp_path / "host.svg"  # the same bytes: only the link differs
    host.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.unlink()
    target.symlink_to(host)
    with pytest.raises(blind.CannotCompare, match="fuori dalla cartella del lavoro"):
        blind.lay_out(blind.assign(found, random.Random(1)), tmp_path / "blind" / "s")


@pytest.mark.parametrize("name", ["Merlo", "merlo_3", "-merlo"])
def test_a_folder_that_is_not_a_project_name_is_no_project(tmp_path: Path, name: str) -> None:
    (path,) = files(tmp_path, {f"projects/{name}/work/exports/segno.svg": MERLO})
    (candidate,) = blind.candidates([path], tmp_path / "projects")
    assert (candidate.judged.project, candidate.judged.file) == ("", str(path.resolve()))


def test_a_file_loose_in_the_projects_folder_is_no_project(tmp_path: Path) -> None:
    (path,) = files(tmp_path, {"projects/logo": MERLO})
    (candidate,) = blind.candidates([path], tmp_path / "projects")
    assert (candidate.judged.project, candidate.judged.file) == ("", str(path.resolve()))


def test_a_projects_folder_reached_through_a_link_is_still_the_projects_folder(tmp_path: Path) -> None:
    (path,) = files(tmp_path, {"real/merlo/work/exports/segno.svg": MERLO})
    (tmp_path / "projects").symlink_to(tmp_path / "real", target_is_directory=True)
    for given in (path, tmp_path / "projects/merlo/work/exports/segno.svg"):
        (candidate,) = blind.candidates([given], tmp_path / "projects")
        assert (candidate.judged.project, candidate.judged.file) == ("merlo", "exports/segno.svg")
