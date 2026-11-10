"""Il confronto alla cieca: copie con la sola lettera nel nome, lettere estratte a ogni confronto.

Chi giudica vede solo `A.svg`, `B.svg`. La corrispondenza tra lettere e file resta in memoria finché il
giudizio non è dato: prima non è scritta da nessuna parte. Le lettere non sono stabili come quelle della
tavola dei critici: a una persona che giudica più volte, lettere ripetute direbbero col tempo chi è chi.
"""

from __future__ import annotations

import hashlib
import os
import random
import secrets
import shutil
import string
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agency.contracts.files import OutsidePerimeter, open_under, sha256_under
from agency.contracts.judgment import Judged, Judgment, Level, Rating, below_the_top
from agency.contracts.project import parse_project_name

LETTERS = string.ascii_uppercase
SAME = {"sì": True, "si": True, "no": False}


class CannotCompare(Exception):
    """I file non si possono confrontare alla pari."""


@dataclass(frozen=True)
class Candidate:
    path: Path
    judged: Judged
    # Set for a file under the projects folder: it is read relative to `root`, never through a link.
    root: Path | None = None
    relative: str = ""


def candidates(paths: list[Path], projects_dir: Path) -> list[Candidate]:
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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _below(path: Path, projects_dir: Path) -> tuple[Path, tuple[str, ...]] | None:
    """The projects folder and the parts of `path` below it, or None for a file elsewhere.

    The path is only made absolute, never resolved: the sandbox can leave a link anywhere below the folder.
    """
    absolute = path.absolute()
    for root in (projects_dir.absolute(), projects_dir.resolve()):
        if root in absolute.parents:
            return projects_dir.resolve(), absolute.relative_to(root).parts
    return None


def _candidate(path: Path, projects_dir: Path) -> Candidate:
    below = _below(path, projects_dir)
    if below is None:  # the operator's own file
        resolved = path.resolve()
        return Candidate(resolved, Judged(project="", file=str(resolved), sha256=_digest(resolved)))
    root, parts = below
    relative = "/".join(parts)
    try:
        digest = sha256_under(root, relative)
    except OutsidePerimeter as exc:
        raise CannotCompare(str(exc)) from exc
    # A file loose in projects/, or in a folder that is not a project name, belongs to no project.
    if len(parts) < 2 or not _is_project_name(parts[0]):
        return Candidate(
            root / relative, Judged(project="", file=str(root / relative), sha256=digest), root, relative
        )
    inside = parts[2:] if parts[1] == "work" else parts[1:]
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
    return secrets.token_hex(4)


def assign(found: list[Candidate], rng: random.Random) -> dict[str, Candidate]:
    """Le lettere vanno in ordine, A, B, C: è l'ordine dei file a essere estratto."""
    drawn = list(found)
    rng.shuffle(drawn)
    return dict(zip(LETTERS, drawn, strict=False))


def lay_out(assigned: dict[str, Candidate], folder: Path) -> list[Path]:
    """Copie nuove, senza i metadati dell'originale: nemmeno la data dice da dove viene un file.

    Ogni copia deve avere l'hash letto all'inizio: si giudica, e si conserva, esattamente quella versione.
    """
    folder.mkdir(parents=True)
    copies = []
    for letter, candidate in assigned.items():
        copy = folder / f"{letter}{candidate.path.suffix.lower()}"
        _copy(candidate, copy)
        if _digest(copy) != candidate.judged.sha256:
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
    """Le lettere la cui copia anonima non ha più l'hash del giudizio: il giudizio può durare minuti."""
    pairs = zip(assigned.items(), copies, strict=True)
    return [letter for (letter, candidate), copy in pairs if _digest(copy) != candidate.judged.sha256]


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
    """Una scelta che contraddice i livelli si spiega e si richiede: di solito è un tasto sbagliato."""
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
