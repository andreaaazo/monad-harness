import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy/claude-code-v1"
CLAUDE = LEGACY / "src/.claude"


def test_legacy_backup_is_frozen() -> None:
    lines = (LEGACY / "MANIFEST.sha256").read_text().splitlines()
    assert lines
    for line in lines:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((LEGACY / name).read_bytes()).hexdigest() == digest, name


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
