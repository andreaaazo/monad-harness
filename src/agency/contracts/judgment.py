"""The blind judgment: a person rates anonymous files without knowing which run they come from."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Level(StrEnum):
    """The reference levels of `docs/07-EVALS.md`."""

    ORDINARY = "ordinario"
    GOOD = "buono"
    EXCELLENT = "eccellente"

    @property
    def rank(self) -> int:
        """Ordinary, good, excellent: the order they are declared in."""
        return list(Level).index(self)


class Rating(BaseModel):
    """The judge's rating of one letter: its level, whether it passes the substitution test, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    letter: str = Field(min_length=1)
    level: Level
    specific: bool = Field(description="Substitution test: it would not hold up under another name")
    why: str = Field(min_length=1)


class Judgment(BaseModel):
    """One comparison: a rating for each letter and, when there is more than one letter, the best."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    judge: str = Field(min_length=1)
    ratings: list[Rating] = Field(min_length=1)
    best: str | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Judgment:
        letters = [rating.letter for rating in self.ratings]
        if len(set(letters)) != len(letters):
            raise ValueError("una lettera ha più di un voto")
        if len(letters) == 1 and self.best is not None:
            raise ValueError("con un solo file non c'è un migliore")
        if len(letters) > 1 and self.best not in letters:
            raise ValueError(f"il migliore deve essere una delle lettere: {', '.join(letters)}")
        if self.best is not None and (reason := below_the_top(self.ratings, self.best)):
            raise ValueError(reason)
        return self


def below_the_top(ratings: list[Rating], best: str) -> str | None:
    """Why `best` cannot be the best, or None if it can: an excellent never loses to a good.

    Otherwise the judgment would not say which mark wins. At the same level, the choice decides (ADR-0041).
    """
    top = max(ratings, key=lambda rating: rating.level.rank).level
    chosen = next(rating for rating in ratings if rating.letter == best)
    if chosen.level == top:
        return None
    higher = ", ".join(rating.letter for rating in ratings if rating.level == top)
    return f"{best} è {chosen.level}, e il livello più alto è {top} ({higher}): il migliore è tra questi"


class Judged(BaseModel):
    """The exact version of the file behind a letter. `project` is empty for a file outside the projects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: str
    file: str = Field(description="Relative to the project's work/, or the full path")
    sha256: str
