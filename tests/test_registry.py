import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agency import registry
from agency.agents.toolbox import TOOLS, Toolbox, role_tools, tools_for
from agency.artifacts import FileStore
from agency.contracts.registry import read_checks, read_org, read_roles
from agency.contracts.ticket import Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.registry import load_rules
from agency.toolkit.base import ToolContext
from agency.workshop.craft import CommandIndex
from agency.workshop.sandbox import Sandbox
from support.rules import RULES

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy/claude-code-v1"
CLAUDE = LEGACY / "src/.claude"
KINDS = {"director", "author", "reviewer", "router"}


def registry_roles() -> dict[str, dict]:
    return json.loads((ROOT / "registry/roles.json").read_text(encoding="utf-8"))["roles"]


def can_open_rows() -> dict[str, list[str]]:
    return json.loads((ROOT / "registry/org.json").read_text(encoding="utf-8"))["can_open"]


def test_legacy_backup_is_frozen() -> None:
    lines = (LEGACY / "MANIFEST.sha256").read_text().splitlines()
    assert lines
    for line in lines:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((LEGACY / name).read_bytes()).hexdigest() == digest, name


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vendored_qa_scripts_match_their_manifest() -> None:
    """The sandbox runs these copies, not the originals: an edit must show up here (STR-014)."""
    scripts = ROOT / "src/agency/qa/scripts"
    manifest = json.loads((ROOT / "tests/fixtures/qa_scripts.json").read_text(encoding="utf-8"))["scripts"]
    assert sorted(path.name for path in scripts.glob("*.py")) == sorted(manifest), "a script without an entry"
    patches = scripts / "PATCHES.md"
    for name, entry in manifest.items():
        assert digest(scripts / name) == entry["sha256"], name
        assert digest(ROOT / entry["legacy"]) == entry["legacy_sha256"], name
        if entry["sha256"] != entry["legacy_sha256"]:
            noted = patches.is_file() and name in patches.read_text(encoding="utf-8")
            assert noted, f"{name} differs from its original and PATCHES.md does not say why"


def test_every_legacy_role_has_a_contract() -> None:
    roles = json.loads((ROOT / "registry/roles.json").read_text())["roles"]
    legacy = {p.stem for p in (CLAUDE / "agents").glob("*.md")} | {"router"}
    assert legacy <= set(roles)
    assert set(roles) - legacy == {"direction-d", "direction-e"}
    assert {r["model"] for r in roles.values()} <= {"claude-opus-5-5", "claude-sonnet-5-5"}


def test_checks_only_name_real_roles() -> None:
    roles = set(json.loads((ROOT / "registry/roles.json").read_text())["roles"])
    checks = json.loads((ROOT / "registry/checks.json").read_text())["checks"]
    for name, spec in checks.items():
        assert set(spec.get("roles", [])) <= roles, name


def test_parity_matrix_covers_everything_in_the_backup() -> None:
    parity = (ROOT / "docs/PARITY.md").read_text()
    items = [f"`{p.stem}`" for p in (CLAUDE / "agents").glob("*.md")]
    items += [f"`{p.name}`" for p in (CLAUDE / "skills").iterdir() if p.is_dir()]
    items += [f"`{p.name}`" for p in (CLAUDE / "scripts").iterdir() if p.is_file()]
    items += [f"`{p.name}`" for p in (CLAUDE / "hooks").iterdir() if p.is_file()]
    items += [f"`{p.name}`" for p in (CLAUDE / "skills").glob("*/scripts/*") if p.is_file()]
    items += [f"`{p.name}`" for p in (CLAUDE / "design-agency").glob("*.md")]
    missing = [item for item in items if item not in parity]
    assert not missing


def test_only_roles_that_open_tickets_get_director_tools() -> None:
    rows = can_open_rows()
    for role in registry_roles():
        assert ("open_ticket" in {tool.name for tool in role_tools(RULES, role)}) == (role in rows), role


def test_tool_declarations_match_the_org_chart() -> None:
    roles = registry_roles()
    kinds = {name: config["tools"] for name, config in roles.items()}
    assert set(kinds.values()) <= KINDS
    assert {name for name, kind in kinds.items() if kind in {"director", "router"}} == set(can_open_rows())
    assert [name for name, kind in kinds.items() if kind == "router"] == ["router"]
    # The reviewers judge the work and never edit it: a role joins them only by a deliberate edit here.
    reviewers = {name for name, kind in kinds.items() if kind == "reviewer"}
    assert reviewers == {"qa-inspector", "critic", "legal-reviewer"}
    assert reviewers == load_rules().reviewers()
    # Five directions explore, in this order (ADR-0013).
    assert list(load_rules().directions().items()) == [(letter, f"direction-{letter}") for letter in "abcde"]
    assert all("department" not in config for config in roles.values())


def spec_of(kind: TicketType, prompt: str = "") -> TicketSpec:
    return TicketSpec(
        title="Prova",
        request="r",
        type=kind,
        sender="d",
        assignee="c",
        outputs=["a"],
        checks={"a": ["master_open"]},
        media=[Medium.VECTOR],
        prompt=prompt,
    )


def craft_box(tmp_path: Path, role: str) -> Toolbox:
    ctx = ToolContext(
        role,
        "p",
        "T-1",
        "i",
        Ledger(tmp_path / "l.sqlite"),
        Sandbox(tmp_path),
        CommandIndex([]),
        FileStore(tmp_path / "artifacts"),
        rules=RULES,
    )
    return Toolbox(ctx, [TOOLS[name] for name in ("craft_search", "craft_describe", "craft_run")])


CRAFT_CALLS = {
    "craft_search": {"query": "cerchio"},
    "craft_describe": {"command": "nessuno"},
    "craft_run": {"document": "a.vectorcraft", "steps": []},
}


def test_craft_tools_follow_the_role_craft_list(tmp_path: Path) -> None:
    roles = registry_roles()
    specs = [spec_of(kind) for kind in TicketType] + [spec_of(TicketType.REVIEW, "critic-board")]
    for role in (name for name, config in roles.items() if not config["craft"]):
        offered = [role_tools(RULES, role)] + [
            tools_for(RULES, role, spec, mode)
            for spec in specs
            for mode in (None, "plan", "select", "present")
        ]
        for tools in offered:
            assert not {tool.name for tool in tools if tool.name.startswith("craft_")}, role
    for role in ("motion-designer", "ux-designer"):
        assert "vectorcraft" not in roles[role]["craft"]
        for name, arguments in CRAFT_CALLS.items():
            result = craft_box(tmp_path, role).call("x", name, arguments)
            assert result["is_error"] and result["content"] == f"{role} non lavora con vectorcraft", (
                role,
                name,
            )
    for name, arguments in CRAFT_CALLS.items():
        result = craft_box(tmp_path, "identity-designer").call("x", name, arguments)
        assert "non lavora con" not in result["content"], name


ROLE = {"tools": "author", "model": "m", "effort": "high", "craft": []}
CHECK = {"kind": "measure", "independent": False}


def write_json(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("reader", "document", "field"),
    [
        (
            read_roles,
            {"roles": {"x": {k: v for k, v in ROLE.items() if k != "craft"} | {"crafts": []}}},
            "crafts",
        ),
        (read_checks, {"checks": {"x": CHECK | {"independant": True}}}, "independant"),
        (read_org, {"can_opn": {"router": ["*"]}}, "can_opn"),
    ],
)
def test_a_misspelt_registry_field_fails_at_load(
    tmp_path: Path, reader: Callable[[Path], object], document: dict, field: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        reader(write_json(tmp_path, document))


def test_an_unknown_check_kind_fails_at_load(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="kind"):
        read_checks(write_json(tmp_path, {"checks": {"x": CHECK | {"kind": "judgment"}}}))


@pytest.mark.parametrize(
    ("role", "field"),
    [(ROLE | {"craft": ["vectorcarft"]}, "craft"), (ROLE | {"tools": "boss"}, "tools")],
)
def test_a_role_with_an_unknown_craft_app_or_tools_kind_fails_at_load(
    tmp_path: Path, role: dict, field: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        read_roles(write_json(tmp_path, {"roles": {"x": role}}))


def test_the_registry_files_validate_and_load_unchanged() -> None:
    for name, reader, key in (
        ("roles", read_roles, "roles"),
        ("checks", read_checks, "checks"),
        ("org", read_org, "can_open"),
    ):
        path = ROOT / f"registry/{name}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        assert "$comment" in document, name
        loaded = reader(path)
        assert {
            entry: value
            if isinstance(value, list)
            else value.model_dump(mode="json", by_alias=True, exclude_unset=True)
            for entry, value in loaded.items()
        } == document[key], name


def test_a_comment_is_accepted_and_any_other_unknown_key_is_refused(tmp_path: Path) -> None:
    read_roles(write_json(tmp_path, {"$comment": "ok", "roles": {"x": ROLE | {"$comment": "ok"}}}))
    with pytest.raises(ValidationError, match="note"):
        read_roles(write_json(tmp_path, {"roles": {"x": ROLE}, "note": "no"}))


@pytest.mark.parametrize(
    ("reader", "document"),
    [
        (read_roles, {"roles": {"x": ROLE | {"extra": 1}}}),
        (read_checks, {"checks": {"x": CHECK | {"extra": 1}}}),
        (read_org, {"can_open": {"router": ["*"]}, "extra": 1}),
    ],
)
def test_an_unknown_key_beside_valid_ones_fails_at_load(
    tmp_path: Path, reader: Callable[[Path], object], document: dict
) -> None:
    with pytest.raises(ValidationError, match="extra"):
        reader(write_json(tmp_path, document))


@pytest.mark.parametrize(
    ("name", "document"),
    [
        ("roles", {"roles": {"x": ROLE | {"extra": 1}}}),
        ("org", {"can_open": {}, "extra": 1}),
        ("checks", {"checks": {"x": CHECK | {"kind": "judgment"}}}),
    ],
)
def test_loading_the_rules_validates_them(tmp_path: Path, name: str, document: dict) -> None:
    """The composition roots load the rules with `load_rules`, which refuses a broken file (ADR-0058)."""
    (tmp_path / "registry").mkdir()
    for file in ("roles", "checks", "org"):
        (tmp_path / f"registry/{file}.json").write_bytes((ROOT / f"registry/{file}.json").read_bytes())
    (tmp_path / f"registry/{name}.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_rules(tmp_path)


def test_the_typed_rules_match_the_registry_files() -> None:
    """The typed rules say exactly what roles.json, org.json and checks.json say (ADR-0058)."""
    rules = load_rules()
    roles, org = registry_roles(), can_open_rows()
    checks = json.loads((ROOT / "registry/checks.json").read_text(encoding="utf-8"))["checks"]
    dumped = {
        name: role.model_dump(mode="json", by_alias=True, exclude_unset=True)
        for name, role in rules.roles.items()
    }
    assert dumped == roles
    assert {
        name: check.model_dump(mode="json", by_alias=True, exclude_unset=True)
        for name, check in rules.checks.items()
    } == checks
    assert rules.org == org
    pairs = [(sender, assignee) for sender in roles for assignee in roles]
    for sender, assignee in pairs:
        allowed = org.get(sender, [])
        assert rules.can_open(sender, assignee) == ("*" in allowed or assignee in allowed), (sender, assignee)
    assert any(not rules.can_open(sender, assignee) for sender, assignee in pairs)
    assert rules.reviewers() == {name for name, role in roles.items() if role["tools"] == "reviewer"}
    directions = [(name.removeprefix("direction-"), name) for name in roles if name.startswith("direction-")]
    assert list(rules.directions().items()) == directions
    assert rules.active == {name for name in roles if (ROOT / "prompts/roles" / f"{name}.md").is_file()}
    assert rules.measurements() == {name for name, check in checks.items() if check["kind"] == "measure"}


def test_no_module_reads_the_role_registry_as_a_global() -> None:
    """The rules are passed to whoever uses them, not reached as module globals (ADR-0058)."""
    names = r"\b(ROLES|ORG|CHECKS|REVIEWERS|DIRECTIONS)\b"
    pattern = re.compile(rf"\bregistry\.{names}|from agency\.registry import .*{names}")
    found = [
        f"{path.relative_to(ROOT)}:{number}"
        for path in (ROOT / "src").rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert found == []
    assert not hasattr(registry, "ROLES")
