"""Il giudizio alla cieca: una persona vota file anonimi, senza sapere da quale esecuzione vengono."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Level(StrEnum):
    """I riferimenti di `docs/07-EVALS.md`."""

    ORDINARY = "ordinario"
    GOOD = "buono"
    EXCELLENT = "eccellente"


class Rating(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    letter: str = Field(min_length=1)
    level: Level
    specific: bool = Field(description="Test di sostituzione: con un altro nome non reggerebbe")
    why: str = Field(min_length=1)


class Judgment(BaseModel):
    """Un confronto: un voto per ogni lettera e, se le lettere sono più d'una, la migliore."""

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
        return self


class Judged(BaseModel):
    """La versione precisa del file dietro una lettera. `project` è vuoto per un file fuori dai progetti."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: str
    file: str = Field(description="Relativo a work/ del progetto, oppure il percorso intero")
    sha256: str
