"""The studio rules of `registry/`, loaded and checked by `load_rules`, and the prompt library lookups."""

from __future__ import annotations

from pathlib import Path

from agency.config import REPO_ROOT
from agency.contracts.registry import StudioRules, read_checks, read_org, read_roles

PROMPTS = REPO_ROOT / "prompts"


def load_rules(root: Path = REPO_ROOT) -> StudioRules:
    """The studio rules of `<root>/registry`, checked. The composition roots load them once and pass them on;
    a role is active when `<root>/prompts/roles` holds its prompt."""
    roles = read_roles(root / "registry/roles.json")
    return StudioRules(
        roles=roles,
        org=read_org(root / "registry/org.json"),
        checks=read_checks(root / "registry/checks.json"),
        active=frozenset(role for role in roles if (root / "prompts/roles" / f"{role}.md").is_file()),
    )


def skill_names() -> list[str]:
    """The skills `read_skill` serves: the folders under prompts/skills that hold a SKILL.md."""
    return sorted(path.parent.name for path in (PROMPTS / "skills").glob("*/SKILL.md"))


def skills_index() -> str:
    """The skill names as the system prompt lists them."""
    return ", ".join(skill_names())
