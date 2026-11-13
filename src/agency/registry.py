"""The studio rules of `registry/`, loaded and checked once, and the lookups on the prompt library."""

from __future__ import annotations

from agency.config import REPO_ROOT
from agency.contracts.registry import read_checks, read_org, read_roles

PROMPTS = REPO_ROOT / "prompts"
ROLES: dict[str, dict] = read_roles(REPO_ROOT / "registry/roles.json")
ORG: dict[str, list[str]] = read_org(REPO_ROOT / "registry/org.json")
CHECKS: dict[str, dict] = read_checks(REPO_ROOT / "registry/checks.json")
# The roles that judge the work and never edit it: those roles.json gives the reviewer's tool set.
REVIEWERS = frozenset(name for name, spec in ROLES.items() if spec["tools"] == "reviewer")
# The explorers in the order roles.json lists them, by the letter after their prefix: the first lever goes to
# the first, and the letter names its folder, its files and its idea.
DIRECTIONS = {name.removeprefix("direction-"): name for name in ROLES if name.startswith("direction-")}


def skill_names() -> list[str]:
    """The skills `read_skill` serves: the folders under prompts/skills that hold a SKILL.md."""
    return sorted(path.parent.name for path in (PROMPTS / "skills").glob("*/SKILL.md"))


def skills_index() -> str:
    """The skill names as the system prompt lists them."""
    return ", ".join(skill_names())


def has_prompt(role: str) -> bool:
    """A role without a prompt has not been ported yet: it cannot receive work."""
    return (PROMPTS / "roles" / f"{role}.md").is_file()


def can_open(sender: str, assignee: str) -> bool:
    """Whether `sender` may open a ticket for `assignee`, by registry/org.json (`*` allows anyone)."""
    allowed = ORG.get(sender, [])
    return "*" in allowed or assignee in allowed
