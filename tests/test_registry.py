import hashlib
import importlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agency.artifacts import FileStore
from agency.contracts.registry import read_checks, read_org, read_roles
from agency.contracts.ticket import REVIEWERS, Medium, TicketSpec, TicketType
from agency.ledger import Ledger
from agency.tools.craft import CommandIndex
from agency.tools.sandbox import Sandbox
from agency.tools.surface import TOOLS, Toolbox, ToolContext, role_tools, tools_for

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
        assert ("open_ticket" in {tool.name for tool in role_tools(role)}) == (role in rows), role


def test_tool_declarations_match_the_org_chart() -> None:
    roles = registry_roles()
    kinds = {name: config["tools"] for name, config in roles.items()}
    assert set(kinds.values()) <= KINDS
    assert {name for name, kind in kinds.items() if kind in {"director", "router"}} == set(can_open_rows())
    assert [name for name, kind in kinds.items() if kind == "router"] == ["router"]
    assert {name for name, kind in kinds.items() if kind == "reviewer"} == REVIEWERS
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
        offered = [role_tools(role)] + [
            tools_for(role, spec, mode) for spec in specs for mode in ("", "plan", "select", "present")
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
        assert reader(path) == document[key], name


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
    ("module", "name", "document"),
    [
        ("agency.registry", "roles", {"roles": {"x": ROLE | {"extra": 1}}}),
        ("agency.registry", "org", {"can_open": {}, "extra": 1}),
        ("agency.registry", "checks", {"checks": {"x": CHECK | {"kind": "judgment"}}}),
    ],
)
def test_the_modules_that_load_the_rules_validate_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, name: str, document: dict
) -> None:
    for file in ("roles", "checks", "org"):
        (tmp_path / "registry").mkdir(exist_ok=True)
        source = ROOT / f"registry/{file}.json"
        (tmp_path / f"registry/{file}.json").write_bytes(source.read_bytes())
    (tmp_path / f"registry/{name}.json").write_text(json.dumps(document), encoding="utf-8")
    loaded = importlib.import_module(module)
    try:
        with monkeypatch.context() as patch:
            patch.setattr("agency.config.REPO_ROOT", tmp_path)
            with pytest.raises(ValidationError):
                importlib.reload(loaded)
    finally:
        importlib.reload(loaded)
