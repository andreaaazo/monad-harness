"""Typed shape of the studio rules in `registry/*.json`, checked once when they are loaded."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckKind(StrEnum):
    OBSERVATION = "observation"
    JUDGEMENT = "judgement"
    MEASURE = "measure"
    READING = "reading"
    REQUIREMENT = "requirement"


class _Entry(BaseModel):
    """A registry object: no unknown key, and the file's own `$comment` is allowed."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(default="", alias="$comment")


class RoleSpec(_Entry):
    tools: Literal["director", "author", "reviewer", "router"]
    model: str
    effort: str
    craft: list[Literal["vectorcraft", "effectcraft", "figcraft", "photocraft"]]


class RolesFile(_Entry):
    roles: dict[str, RoleSpec]


class CheckSpec(_Entry):
    kind: CheckKind
    independent: bool
    roles: list[str] = []
    observed: bool = False


class ChecksFile(_Entry):
    checks: dict[str, CheckSpec]


class OrgFile(_Entry):
    can_open: dict[str, list[str]]


def _parse(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_roles(path: Path) -> dict[str, RoleSpec]:
    """Validate the roles file and return its roles, typed, in the file's order."""
    return RolesFile.model_validate(_parse(path)).roles


def read_checks(path: Path) -> dict[str, CheckSpec]:
    """Validate the checks file and return its checks, typed, in the file's order."""
    return ChecksFile.model_validate(_parse(path)).checks


def read_org(path: Path) -> dict[str, list[str]]:
    """Validate the org file and return its raw `can_open` object, unchanged."""
    data = _parse(path)
    OrgFile.model_validate(data)
    return data["can_open"]


class StudioRules(BaseModel):
    """The studio's rules from `registry/`, loaded once by the composition roots and passed to whoever uses
    them, never reached as a module global (ADR-0058)."""

    model_config = ConfigDict(frozen=True)

    roles: dict[str, RoleSpec]
    org: dict[str, list[str]]
    checks: dict[str, CheckSpec]
    active: frozenset[str]  # the roles with a prompt: one without has not been ported and cannot receive work

    def can_open(self, sender: str, assignee: str) -> bool:
        """Whether `sender` may open a ticket for `assignee`, by org.json (`*` allows anyone)."""
        allowed = self.org.get(sender, [])
        return "*" in allowed or assignee in allowed

    def reviewers(self) -> frozenset[str]:
        """The roles that judge the work and never edit it: those roles.json gives the reviewer's tool set."""
        return frozenset(name for name, spec in self.roles.items() if spec.tools == "reviewer")

    def directions(self) -> dict[str, str]:
        """The explorers in the order roles.json lists them, by the letter after their prefix: the first lever
        goes to the first, and the letter names its folder, its files and its idea."""
        return {name.removeprefix("direction-"): name for name in self.roles if name.startswith("direction-")}

    def kind_of(self, check: str) -> CheckKind | None:
        """The kind of a registry check, or None for a name the registry does not list."""
        spec = self.checks.get(check)
        return spec.kind if spec else None

    def measurements(self) -> frozenset[str]:
        """The checks that measure: they also pass as MEASURED."""
        return frozenset(name for name, spec in self.checks.items() if spec.kind is CheckKind.MEASURE)
