"""The blind comparison: copies named by their letter alone, with the letters drawn anew for each comparison.

The judge sees only `A.svg`, `B.svg`. The mapping from letters to files stays in memory until the judgment
is given: before that it is written nowhere. The letters are not stable like those of the critics' board:
for a person who judges many times, repeated letters would in time give away which is which.
"""

from __future__ import annotations

import os
import random
import secrets
import shutil
import string
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agency.contracts.files import OutsidePerimeter, file_sha256, land, open_under, sha256_under
from agency.contracts.judgment import Judged, Judgment, Level, Rating, below_the_top
from agency.contracts.layout import WORK
from agency.contracts.project import parse_project_name

LETTERS = string.ascii_uppercase
SAME = {"sì": True, "si": True, "no": False}


class CannotCompare(Exception):
    """The files cannot be compared on equal terms. The message says why, and the CLI prints it."""


@dataclass(frozen=True)
class Candidate:
    """A file to judge: where it is read from, and the exact version the judgment records."""

    path: Path
    judged: Judged
    # Set for a file under the projects folder: it is read relative to `root`, never through a link.
    root: Path | None = None
    relative: str = ""


def candidates(paths: list[Path], projects_dir: Path) -> list[Candidate]:
    """The files, if they can be compared: all present, at most 26, of one type, and no two identical."""
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise CannotCompare(f"file non trovato: {', '.join(missing)}")
    if len(paths) > len(LETTERS):
        raise CannotCompare(f"al massimo {len(LETTERS)} file per confronto")
    kinds = sorted({path.suffix.lower() for path in paths})
    if len(kinds) > 1:
        raise CannotCompare(f"tipi diversi ({', '.join(kinds)}): si confrontano file dello stesso tipo")
    found = [_candidate(path, projects_dir) for path in paths]
    hashes = [candidate.judged.sha256 for candidate in found]
    if len(set(hashes)) < len(hashes):
        raise CannotCompare("due file sono identici: lo stesso contenuto avrebbe due voti")
    return found


def _candidate(path: Path, projects_dir: Path) -> Candidate:
    """The file as the kernel finds it. Below the projects folder it is read only through the no-follow
    helpers, and a link a sandbox left there is refused whatever spelling reaches it (`land`)."""
    try:
        landing = land(path, projects_dir)
    except OutsidePerimeter as exc:
        raise CannotCompare(str(exc)) from exc
    if not landing.parts:  # the operator's own file
        real = landing.real
        return Candidate(real, Judged(project="", file=str(real), sha256=file_sha256(real)))
    root, parts = landing.root, landing.parts
    relative = "/".join(parts)
    try:
        digest = sha256_under(root, relative)
    except OutsidePerimeter as exc:
        raise CannotCompare(str(exc)) from exc
    except FileNotFoundError:
        raise CannotCompare(f"file non trovato: {path}") from None
    # A file loose in projects/, or in a folder that is not a project name, belongs to no project.
    if len(parts) < 2 or not _is_project_name(parts[0]):
        return Candidate(
            root / relative, Judged(project="", file=str(root / relative), sha256=digest), root, relative
        )
    inside = parts[2:] if parts[1] == WORK else parts[1:]
    return Candidate(
        root / relative, Judged(project=parts[0], file="/".join(inside), sha256=digest), root, relative
    )


def _is_project_name(text: str) -> bool:
    try:
        parse_project_name(text)
    except ValueError:
        return False
    return True


def comparison_id() -> str:
    """A random id for one comparison: it names the anonymous folder and groups the judgment's rows."""
    return secrets.token_hex(4)


def assign(found: list[Candidate], rng: random.Random) -> dict[str, Candidate]:
    """The letters go in order, A, B, C: it is the order of the files that is drawn."""
    drawn = list(found)
    rng.shuffle(drawn)
    return dict(zip(LETTERS, drawn, strict=False))


def lay_out(assigned: dict[str, Candidate], folder: Path) -> list[Path]:
    """New copies, without the original's metadata: not even the date tells where a file comes from.

    Each copy must have the hash read at the start: exactly that version is judged, and kept.
    """
    folder.mkdir(parents=True)
    copies = []
    for letter, candidate in assigned.items():
        copy = folder / f"{letter}{candidate.path.suffix.lower()}"
        _copy(candidate, copy)
        if file_sha256(copy) != candidate.judged.sha256:
            raise CannotCompare(f"{candidate.path} è cambiato mentre lo copiavo: riprova quando è fermo")
        copies.append(copy)
    return copies


def _copy(candidate: Candidate, copy: Path) -> None:
    if candidate.root is None:
        shutil.copyfile(candidate.path, copy)
        return
    try:
        source = os.fdopen(open_under(candidate.root, candidate.relative, os.O_RDONLY), "rb")
    except OutsidePerimeter as exc:
        raise CannotCompare(str(exc)) from exc
    with source, copy.open("xb") as target:
        shutil.copyfileobj(source, target)


def changed(assigned: dict[str, Candidate], copies: list[Path]) -> list[str]:
    """The letters whose anonymous copy no longer has its hash: a judgment can take minutes."""
    pairs = zip(assigned.items(), copies, strict=True)
    return [letter for (letter, candidate), copy in pairs if file_sha256(copy) != candidate.judged.sha256]


def _choose[T](ask: Callable[[str], str], prompt: str, options: dict[str, T]) -> T:
    while True:
        answer = ask(prompt).strip().lower()
        if answer in options:
            return options[answer]


def _reason(ask: Callable[[str], str], prompt: str) -> str:
    while True:
        answer = ask(prompt).strip()
        if answer:
            return answer


def interview(letters: list[str], ask: Callable[[str], str], judge: str) -> Judgment:
    """Asks for each letter's level, substitution test and reason, then for the best; it repeats a question
    until the answer is valid."""
    levels = {level.value: level for level in Level}
    ratings = []
    for letter in letters:
        level = _choose(ask, f"Livello di {letter} ({', '.join(levels)}): ", levels)
        same = _choose(ask, f"Con un altro nome {letter} reggerebbe lo stesso? (sì, no): ", SAME)
        why = _reason(ask, f"Perché {letter}? ")
        ratings.append(Rating(letter=letter, level=level, specific=not same, why=why))
    best = _best(ask, ratings) if len(letters) > 1 else None
    return Judgment(judge=judge, ratings=ratings, best=best)


def _best(ask: Callable[[str], str], ratings: list[Rating]) -> str:
    """A choice that contradicts the levels is explained and asked again: it is usually a wrong key."""
    letters = [rating.letter for rating in ratings]
    question = f"Il migliore tra {', '.join(letters)}: "
    prompt = question
    while True:
        best = _choose(ask, prompt, {letter.lower(): letter for letter in letters})
        reason = below_the_top(ratings, best)
        if reason is None:
            return best
        escape = "Per cambiare un livello interrompi con Ctrl-C, e non si registra nulla."
        prompt = f"{reason}. {escape}\n{question}"
