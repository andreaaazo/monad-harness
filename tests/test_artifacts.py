"""Artifacts by hash: every delivered, presented or judged version stays recoverable (M1.6, item 7)."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

import pytest

from agency import cli
from agency.artifacts import FileStore, keeping
from agency.config import Settings
from agency.contracts.artifact import ArtifactMissing, Blob, Origin
from agency.contracts.ticket import Action, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import Sandbox
from agency.tools.surface import Toolbox, ToolContext


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def put(store: FileStore, source: Path) -> Blob:
    with source.open("rb") as handle:
        return store.put(handle)


# The store


def test_a_kept_file_lives_under_its_hash_and_cannot_be_changed(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "artifacts")
    blob = put(store, write(tmp_path / "segno.svg", b"<svg>uno</svg>"))
    assert (blob.sha256, blob.size) == (sha(b"<svg>uno</svg>"), 14)
    location = tmp_path / "artifacts" / blob.sha256[:2] / blob.sha256
    assert location.read_bytes() == b"<svg>uno</svg>"
    assert not location.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    with store.open(blob.sha256) as handle:
        assert handle.read() == b"<svg>uno</svg>"


def test_the_same_content_is_kept_once(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "artifacts")
    first = put(store, write(tmp_path / "a/segno.svg", b"stesso"))
    second = put(store, write(tmp_path / "b/altro.svg", b"stesso"))
    assert first == second
    assert [path.name for path in (tmp_path / "artifacts").rglob("*") if path.is_file()] == [first.sha256]


def test_a_large_file_is_hashed_as_a_whole_and_leaves_nothing_half_written(tmp_path: Path) -> None:
    data = bytes(range(256)) * 20_000  # 5 MB: several read blocks
    store = FileStore(tmp_path / "artifacts")
    blob = put(store, write(tmp_path / "scena.blend", data))
    assert blob.sha256 == sha(data) and blob.size == len(data)
    assert list((tmp_path / "artifacts" / ".incoming").iterdir()) == []


def test_unknown_hash_is_missing_and_a_malformed_one_is_refused(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "artifacts")
    with pytest.raises(ArtifactMissing):
        store.open("a" * 64)
    for bad in ("../../etc/passwd", "abc", "A" * 64):
        with pytest.raises(ValueError):
            store.open(bad)
    assert not store.exists("a" * 64)


def test_intact_notices_a_damaged_or_missing_blob(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "artifacts")
    blob = put(store, write(tmp_path / "segno.svg", b"originale"))
    assert store.intact(blob.sha256)
    location = tmp_path / "artifacts" / blob.sha256[:2] / blob.sha256
    location.chmod(0o644)
    location.write_bytes(b"alterato")
    assert not store.intact(blob.sha256)
    location.unlink()
    assert not store.intact(blob.sha256)


def test_keeping_again_repairs_a_damaged_blob(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "artifacts")
    source = write(tmp_path / "segno.svg", b"originale")
    blob = put(store, source)
    location = tmp_path / "artifacts" / blob.sha256[:2] / blob.sha256
    location.chmod(0o644)
    location.write_bytes(b"rotto")
    assert put(store, source) == blob
    assert store.intact(blob.sha256)


# Keeping and recording


def test_keep_stores_and_records_where_each_version_came_from(tmp_path: Path) -> None:
    store, ledger = FileStore(tmp_path / "artifacts"), Ledger(tmp_path / "l.sqlite")
    work = tmp_path / "work"
    write(work / "exports/segno.svg", b"<svg/>")
    hashes = keeping.keep(
        store,
        ledger,
        work,
        {"exports/segno.svg": "exports/segno.svg"},
        project="merlo4",
        origin=Origin.DELIVERY,
        ticket_id="T-0008",
        run=None,
    )
    assert hashes == {"exports/segno.svg": sha(b"<svg/>")}
    (row,) = ledger.artifacts("merlo4")
    assert (row.sha256, row.path, row.origin, row.ticket_id, row.run) == (
        sha(b"<svg/>"),
        "exports/segno.svg",
        "consegna",
        "T-0008",
        None,
    )
    assert (row.media_type, row.size) == ("image/svg+xml", 6)


def test_keeping_the_same_version_twice_records_it_once(tmp_path: Path) -> None:
    store, ledger = FileStore(tmp_path / "artifacts"), Ledger(tmp_path / "l.sqlite")
    write(tmp_path / "segno.svg", b"<svg/>")
    files = {"segno.svg": "segno.svg"}
    for _ in range(2):  # the resume repeats the step
        keeping.keep(
            store, ledger, tmp_path, files, project="p", origin=Origin.DELIVERY, ticket_id="T-1", run=None
        )
    assert len(ledger.artifacts("p")) == 1


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("exports/segno.svg", "image/svg+xml"),
        ("presentation/r1/presentazione.pdf", "application/pdf"),
        ("construction.md", "text/markdown"),
        ("proposals/r1/x/proposta-x.png", "image/png"),
        ("source/segno.vectorcraft", "application/octet-stream"),
    ],
)
def test_media_type_does_not_depend_on_the_machine(name: str, expected: str) -> None:
    assert keeping.media_type(name) == expected


@pytest.mark.parametrize("statement", ["UPDATE artifacts SET path = 'altro'", "DELETE FROM artifacts"])
def test_artifacts_are_append_only(tmp_path: Path, statement: str) -> None:
    store, ledger = FileStore(tmp_path / "artifacts"), Ledger(tmp_path / "l.sqlite")
    write(tmp_path / "segno.svg", b"<svg/>")
    files = {"segno.svg": "segno.svg"}
    keeping.keep(
        store, ledger, tmp_path, files, project="p", origin=Origin.DELIVERY, ticket_id="T-1", run=None
    )
    with ledger.engine.begin() as connection, pytest.raises(Exception, match="solo in aggiunta"):
        connection.exec_driver_sql(statement)


# The deliveries


def note_ticket(tmp_path: Path) -> tuple[Toolbox, ToolContext, Ledger, Path, str]:
    work = tmp_path / "work"
    write(work / "nota.md", b"v1")
    ledger = Ledger(tmp_path / "l.sqlite")
    spec = TicketSpec(
        title="Nota",
        request="r",
        type=TicketType.PRODUCTION,
        sender="design-director",
        assignee="copywriter",
        outputs=["nota.md"],
        checks={"*.md": ["req:letta"]},
        media=[Medium.NONE],
        medium_why="solo un testo di prova",
    )
    ticket = ledger.open(spec, "p")
    store = FileStore(tmp_path / "artifacts")
    context = ToolContext(
        "copywriter", "p", ticket, "i", ledger, Sandbox(work), CommandIndex([]), store, run=None
    )
    return Toolbox(context), context, ledger, work, ticket


def deliver(box: Toolbox, name: str) -> dict:
    requirement = {"file": "nota.md", "check": "req:letta", "result": "PASS", "note": "ok"}
    box.call(f"{name}-req", "record_requirement", requirement)
    return box.call(name, "deliver", {"note": name, "verdict": None})


def test_every_delivered_version_stays_even_after_the_file_is_overwritten(tmp_path: Path) -> None:
    box, context, ledger, work, ticket = note_ticket(tmp_path)
    assert not deliver(box, "prima").get("is_error")
    first = ledger.delivered(ticket)["nota.md"]
    ledger.apply(ticket, Action.REWORK, "design-director", "cambia il titolo")
    context.finished = None
    (work / "nota.md").write_bytes(b"v2")
    assert not deliver(box, "seconda").get("is_error")
    second = ledger.delivered(ticket)["nota.md"]

    store = FileStore(tmp_path / "artifacts")
    assert first != second
    for digest, content in ((first, b"v1"), (second, b"v2")):
        with store.open(digest) as handle:
            assert handle.read() == content
    kept = [(row.sha256, row.origin, row.ticket_id) for row in ledger.artifacts("p")]
    assert kept == [(first, "consegna", ticket), (second, "consegna", ticket)]


def test_a_refused_delivery_keeps_nothing(tmp_path: Path) -> None:
    box, _, ledger, _, _ = note_ticket(tmp_path)
    assert box.call("a", "deliver", {"note": "senza requisito", "verdict": None})["is_error"]
    assert ledger.artifacts("p") == []
    assert not (tmp_path / "artifacts").exists()


# The commands


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AGENCY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENCY_PROJECTS_DIR", str(tmp_path / "projects"))
    return Settings(_env_file=None)  # type: ignore[call-arg]


def kept(studio: Settings, tmp_path: Path, data: bytes, path: str = "source/segno.vectorcraft") -> str:
    store, ledger = FileStore(studio.layout.artifacts), Ledger(studio.layout.ledger)
    work = tmp_path / "projects/merlo4/work"
    write(work / path, data)
    return keeping.keep(
        store,
        ledger,
        work,
        {path: path},
        project="merlo4",
        origin=Origin.DELIVERY,
        ticket_id="T-0008",
        run=None,
    )[path]


def test_artifacts_lists_the_versions_of_a_project(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master")
    assert cli.main(["artifacts", "merlo4"]) == 0
    out = capsys.readouterr().out
    assert "merlo4: 1 versione conservata" in out
    assert f"{digest[:12]}  consegna  T-0008  6 B  source/segno.vectorcraft" in out


def test_restore_brings_back_an_overwritten_master(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master buono")
    master = tmp_path / "projects/merlo4/work/source/segno.vectorcraft"
    master.write_bytes(b"sovrascritto da un comando sbagliato")
    target = tmp_path / "ripristino/segno.vectorcraft"

    assert cli.main(["restore", digest[:12], str(target)]) == 0

    assert target.read_bytes() == b"master buono"
    assert target.stat().st_mode & stat.S_IWUSR  # the restored copy can be worked on
    assert "consegna di T-0008, merlo4: source/segno.vectorcraft" in capsys.readouterr().out


def test_restore_accepts_a_hash_copied_in_capitals(studio: Settings, tmp_path: Path) -> None:
    digest = kept(studio, tmp_path, b"master")
    assert cli.main(["restore", f" {digest[:12].upper()} ", str(tmp_path / "copia.vectorcraft")]) == 0
    assert (tmp_path / "copia.vectorcraft").read_bytes() == b"master"


def test_restore_never_overwrites(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master")
    target = write(tmp_path / "esiste.vectorcraft", b"da non perdere")
    assert cli.main(["restore", digest, str(target)]) == 1
    assert target.read_bytes() == b"da non perdere"
    assert "esiste già" in capsys.readouterr().out


@pytest.mark.parametrize(("prefix", "message"), [("0" * 12, "nessuna versione"), ("zz", "esadecimal")])
def test_restore_explains_an_unknown_or_malformed_hash(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str], prefix: str, message: str
) -> None:
    kept(studio, tmp_path, b"master")
    assert cli.main(["restore", prefix, str(tmp_path / "x")]) == 1
    assert message in capsys.readouterr().out


def sharing_the_first_digit() -> tuple[bytes, bytes]:
    """Two contents whose hashes share the first hex digit: 17 contents always hold such a pair, as there are
    only 16 digits."""
    seen: dict[str, bytes] = {}
    for number in range(17):
        data = f"versione {number}".encode()
        if (digit := sha(data)[0]) in seen:
            return seen[digit], data
        seen[digit] = data
    raise AssertionError("seventeen hashes over sixteen digits: two always share one")


def test_restore_refuses_an_ambiguous_prefix(
    studio: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(keeping, "MIN_PREFIX", 1)
    one, other = sharing_the_first_digit()
    kept(studio, tmp_path, one, "a.md")
    kept(studio, tmp_path, other, "b.md")
    assert cli.main(["restore", sha(one)[0], str(tmp_path / "x")]) == 1
    assert "ambiguo" in capsys.readouterr().out


def test_restore_refuses_a_prefix_too_short_to_be_safe(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master")
    assert cli.main(["restore", digest[:4], str(tmp_path / "x")]) == 1
    assert "almeno" in capsys.readouterr().out


@pytest.mark.parametrize("damage", ["alterata", "mancante"])
def test_restore_of_a_damaged_version_leaves_no_file(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str
) -> None:
    digest = kept(studio, tmp_path, b"master")
    location = studio.layout.artifacts / digest[:2] / digest
    location.chmod(0o644)
    if damage == "alterata":
        location.write_bytes(b"alterato")
    else:
        location.unlink()
    target = tmp_path / "ripristino.vectorcraft"
    assert cli.main(["restore", digest, str(target)]) == 1
    assert not target.exists()
    assert "agency verify" in capsys.readouterr().out


def test_verify_finds_a_damaged_artifact(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master")
    assert cli.main(["verify"]) == 0
    assert "artefatti integri: 1" in capsys.readouterr().out
    location = studio.layout.artifacts / digest[:2] / digest
    location.chmod(0o644)
    location.write_bytes(b"alterato")
    assert cli.main(["verify"]) == 1
    out = capsys.readouterr().out
    assert "ARTEFATTI DANNEGGIATI" in out and digest[:12] in out and "source/segno.vectorcraft" in out


def test_restore_refuses_a_link_inside_the_projects_folder(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = kept(studio, tmp_path, b"master")
    host = tmp_path / "host"
    host.mkdir()
    (tmp_path / "projects/merlo4/work/exports").symlink_to(host, target_is_directory=True)
    target = tmp_path / "projects/merlo4/work/exports/nuova/segno.vectorcraft"
    assert cli.main(["restore", digest, str(target)]) == 1
    assert list(host.iterdir()) == []
    assert "fuori dalla cartella del lavoro" in capsys.readouterr().out


def test_restore_refuses_a_link_inside_the_projects_folder_named_through_dotdot(
    studio: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A `..` in the typed path must not move the destination out of the projects folder's no-follow rule.
    digest = kept(studio, tmp_path, b"master")
    host = tmp_path / "host"
    host.mkdir()
    (tmp_path / "projects/merlo4/work/exports").symlink_to(host, target_is_directory=True)
    (tmp_path / "elsewhere").mkdir()
    target = tmp_path / "elsewhere/../projects/merlo4/work/exports/segno.vectorcraft"
    assert cli.main(["restore", digest, str(target)]) == 1
    assert list(host.iterdir()) == []
    assert "fuori dalla cartella del lavoro" in capsys.readouterr().out


def test_restore_follows_a_link_outside_the_projects_folder(studio: Settings, tmp_path: Path) -> None:
    digest = kept(studio, tmp_path, b"master")
    real = tmp_path / "real-home"
    real.mkdir()
    (tmp_path / "home").symlink_to(real, target_is_directory=True)
    assert cli.main(["restore", digest, str(tmp_path / "home/nuova/segno.vectorcraft")]) == 0
    assert (real / "nuova/segno.vectorcraft").read_bytes() == b"master"


def test_restore_creates_the_missing_folders_inside_the_projects_folder(
    studio: Settings, tmp_path: Path
) -> None:
    digest = kept(studio, tmp_path, b"master")
    assert cli.main(["restore", digest, str(tmp_path / "projects/merlo4/work/nuova/segno.vectorcraft")]) == 0
    assert cli.main(["restore", digest, str(tmp_path / "projects/segno.vectorcraft")]) == 0
    assert (tmp_path / "projects/merlo4/work/nuova/segno.vectorcraft").read_bytes() == b"master"
    assert (tmp_path / "projects/segno.vectorcraft").read_bytes() == b"master"
