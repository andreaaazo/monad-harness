"""Il giudizio alla cieca di una persona, legato allo sha256 del file giudicato (M1.6, punto 5)."""

from __future__ import annotations

import hashlib
import os
import random
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agency import cli
from agency.config import Settings
from agency.contracts.judgment import Judged, Judgment, Level, Rating
from agency.evaluation import blind
from agency.ledger import Ledger
from agency.telemetry import report


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


def two_projects(tmp_path: Path) -> list[Path]:
    return files(
        tmp_path,
        {
            "projects/merlo/work/exports/segno.svg": "<svg>merlo</svg>",
            "projects/merlo3/work/exports/segno.svg": "<svg>merlo3</svg>",
        },
    )


def test_candidates_know_project_file_and_hash(tmp_path: Path) -> None:
    found = blind.candidates(two_projects(tmp_path), tmp_path / "projects")
    assert [candidate.judged for candidate in found] == [
        Judged(
            project="merlo", file="exports/segno.svg", sha256=hashlib.sha256(b"<svg>merlo</svg>").hexdigest()
        ),
        Judged(
            project="merlo3",
            file="exports/segno.svg",
            sha256=hashlib.sha256(b"<svg>merlo3</svg>").hexdigest(),
        ),
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
    answers = ["ottimo", "buono", "forse", "si", "  ", "Regge", "eccellente", "no", "Unico", "C", "a"]
    judgment = blind.interview(["A", "B"], scripted(answers), "andrea")
    assert judgment.ratings == [
        Rating(letter="A", level=Level.GOOD, specific=False, why="Regge"),
        Rating(letter="B", level=Level.EXCELLENT, specific=True, why="Unico"),
    ]
    assert judgment.best == "A"


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
    with pytest.raises(ValueError, match="lettere"):
        ledger.record_judgment("s1", judgment, {"A": origins["A"]})
    assert ledger.comparison("s1") == []


@pytest.mark.parametrize("statement", ["UPDATE judgments SET level = 'eccellente'", "DELETE FROM judgments"])
def test_judgments_are_append_only(tmp_path: Path, statement: str) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_judgment("s1", *comparison())
    with ledger.engine.begin() as connection, pytest.raises(Exception, match="solo in aggiunta"):
        connection.exec_driver_sql(statement)


def test_report_of_a_project_shows_its_judgments(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record_judgment("s1", *comparison())
    text = report.render(ledger, "merlo3")
    assert "Giudizi alla cieca:" in text
    assert "exports/segno.svg [B] eccellente, specifico, il migliore di 2" in text


# Il comando


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.chdir(tmp_path)
    return Settings(_env_file=None)  # type: ignore[call-arg]


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
    assert seen[0] == ["A.svg", "B.svg"]
    assert "merlo" not in out.split("Registrati")[0]
    assert "Registrati 2 giudizi di andrea" in out
    ledger = Ledger(studio.ledger_path)
    rows = ledger.judgments("merlo") + ledger.judgments("merlo3")
    assert sorted((row.level, row.best) for row in rows) == [("buono", True), ("ordinario", False)]
    best = next(row for row in rows if row.best)
    assert f"A buono, specifico, il migliore: exports/segno.svg di {best.project}" in out
    assert list(Path("data/blind").iterdir()) == []


def test_interrupted_judgment_records_nothing_and_leaves_no_copies(
    studio: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = two_projects(Path.cwd())
    answer(monkeypatch, ["buono"], [])

    assert cli.main(["judge", *map(str, paths)]) == 1

    assert "nulla registrato" in capsys.readouterr().out
    ledger = Ledger(studio.ledger_path)
    assert ledger.judgments("merlo") == [] and ledger.judgments("merlo3") == []
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
