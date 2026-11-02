"""Il confronto alla cieca: copie con la sola lettera nel nome, lettere estratte a ogni confronto.

Chi giudica vede solo `A.svg`, `B.svg`. La corrispondenza tra lettere e file resta in memoria finché il
giudizio non è dato: prima non è scritta da nessuna parte. Le lettere non sono stabili come quelle della
tavola dei critici: a una persona che giudica più volte, lettere ripetute direbbero col tempo chi è chi.
"""

from __future__ import annotations

import hashlib
import random
import secrets
import shutil
import string
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agency.contracts.judgment import Judged, Judgment, Level, Rating

LETTERS = string.ascii_uppercase
SAME = {"sì": True, "si": True, "no": False}


class CannotCompare(Exception):
    """I file non si possono confrontare alla pari."""


@dataclass(frozen=True)
class Candidate:
    path: Path
    judged: Judged


def candidates(paths: list[Path], projects_dir: Path) -> list[Candidate]:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise CannotCompare(f"file non trovato: {', '.join(missing)}")
    if len(paths) > len(LETTERS):
        raise CannotCompare(f"al massimo {len(LETTERS)} file per confronto")
    kinds = sorted({path.suffix.lower() for path in paths})
    if len(kinds) > 1:
        raise CannotCompare(f"tipi diversi ({', '.join(kinds)}): si confrontano file dello stesso tipo")
    found = [Candidate(path.resolve(), _judged(path.resolve(), projects_dir.resolve())) for path in paths]
    hashes = [candidate.judged.sha256 for candidate in found]
    if len(set(hashes)) < len(hashes):
        raise CannotCompare("due file sono identici: lo stesso contenuto avrebbe due voti")
    return found


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _judged(path: Path, projects_dir: Path) -> Judged:
    digest = _digest(path)
    if projects_dir not in path.parent.parents:  # un file sciolto in projects/ non è di nessun progetto
        return Judged(project="", file=str(path), sha256=digest)
    project, *rest = path.relative_to(projects_dir).parts
    inside = rest[1:] if rest[:1] == ["work"] else rest
    return Judged(project=project, file="/".join(inside), sha256=digest)


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
        shutil.copyfile(candidate.path, copy)
        if _digest(copy) != candidate.judged.sha256:
            raise CannotCompare(f"{candidate.path} è cambiato mentre lo copiavo: riprova quando è fermo")
        copies.append(copy)
    return copies


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
    best = None
    if len(letters) > 1:
        best = _choose(
            ask, f"Il migliore tra {', '.join(letters)}: ", {item.lower(): item for item in letters}
        )
    return Judgment(judge=judge, ratings=ratings, best=best)
