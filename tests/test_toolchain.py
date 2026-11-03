"""Gli strumenti locali hanno una versione sola, scritta in mise.toml (ADR-0034)."""

from __future__ import annotations

import json
import re
import tomllib

from agency.config import REPO_ROOT

MISE = tomllib.loads((REPO_ROOT / "mise.toml").read_text(encoding="utf-8"))
WEB = json.loads((REPO_ROOT / "web" / "package.json").read_text(encoding="utf-8"))


def version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def test_mise_pins_every_tool_to_an_exact_version() -> None:
    tools = MISE["tools"]
    assert set(tools) == {"node", "pnpm", "uv", "task"}
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", value) for value in tools.values())


def test_pnpm_is_the_same_for_mise_and_for_the_web_project() -> None:
    assert WEB["packageManager"] == f"pnpm@{MISE['tools']['pnpm']}"


def test_node_satisfies_what_next_js_asks_for() -> None:
    minimum = WEB["engines"]["node"].removeprefix(">=")
    assert version(MISE["tools"]["node"]) >= version(minimum)


def test_python_stays_with_uv_not_with_mise() -> None:
    """Un solo proprietario: Python lo sceglie pyproject.toml e lo installa uv."""
    assert "python" not in MISE["tools"]


def test_mise_never_loads_dotenv_into_the_shell() -> None:
    """La chiave API sta in .env, che legge solo il gateway: nell'ambiente arriverebbe a ogni processo."""
    environment = MISE.get("env", {})
    assert "_" not in environment or "file" not in environment["_"]
    assert environment.get("NEXT_TELEMETRY_DISABLED") == "1"
    assert not any("ANTHROPIC" in name for name in environment)
