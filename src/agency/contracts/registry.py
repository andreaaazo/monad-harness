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


def read_roles(path: Path) -> dict[str, dict]:
    """Validate the roles file and return its raw `roles` object, unchanged."""
    data = _parse(path)
    RolesFile.model_validate(data)
    return data["roles"]


def read_checks(path: Path) -> dict[str, dict]:
    """Validate the checks file and return its raw `checks` object, unchanged."""
    data = _parse(path)
    ChecksFile.model_validate(data)
    return data["checks"]


def read_org(path: Path) -> dict[str, list[str]]:
    """Validate the org file and return its raw `can_open` object, unchanged."""
    data = _parse(path)
    OrgFile.model_validate(data)
    return data["can_open"]
