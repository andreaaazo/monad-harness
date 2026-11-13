"""Values that files in different languages must spell alike, since no import can share them (STR-011).

The API key names have their owner in `agency.contracts.secrets`. The web scripts remove them before Next.js
starts, Playwright plants a fake key in each, and the defense check looks for the removal. The e2e Django port
and the e2e build folder are spelled in the web scripts, the Playwright config, a spec, tsconfig.json and
.gitignore.
"""

from __future__ import annotations

import json
import re

from agency.config import REPO_ROOT
from agency.contracts.secrets import API_KEY_VARIABLES

SCRIPTS: dict[str, str] = json.loads((REPO_ROOT / "web/package.json").read_text(encoding="utf-8"))["scripts"]
REMOVED = re.compile(r"env((?: -u \w+)+)")


def text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def found(pattern: str, source: str) -> str:
    match = re.search(pattern, source)
    assert match is not None, pattern
    return match[1]


def test_every_command_that_removes_the_key_removes_every_name() -> None:
    sources = {
        "web/package.json": " ".join(SCRIPTS.values()),
        "web/playwright.config.ts": text("web/playwright.config.ts"),
        "web/scripts/check-defenses.mjs": text("web/scripts/check-defenses.mjs"),
    }
    for name, source in sources.items():
        removals = {frozenset(group.split(" -u ")[1:]) for group in REMOVED.findall(source)}
        assert removals == {frozenset(API_KEY_VARIABLES)}, name


def test_playwright_plants_the_fake_key_in_every_name() -> None:
    planted = set(re.findall(r"(\w+): CANARY", text("web/playwright.config.ts")))
    assert planted == set(API_KEY_VARIABLES)


def test_the_e2e_django_port_is_the_same_everywhere() -> None:
    """The e2e build bakes the API origin into its rewrites, so the server must listen exactly there."""
    port = found(r"AGENCY_API_ORIGIN=http://127\.0\.0\.1:(\d+)", SCRIPTS["build:e2e"])
    playwright = text("web/playwright.config.ts")
    assert found(r'const DJANGO = "http://127\.0\.0\.1:(\d+)"', playwright) == port
    assert found(r"agency-server --port (\d+)", playwright) == port
    assert found(r"const DJANGO_PORT = (\d+);", text("web/e2e/run.spec.ts")) == port


def test_the_e2e_build_folder_is_the_same_everywhere() -> None:
    folder = found(r"AGENCY_NEXT_DIST=(\S+)", SCRIPTS["build:e2e"])
    assert set(re.findall(r"node (\S+)/standalone/server\.js", text("web/playwright.config.ts"))) == {folder}
    assert f'join(process.cwd(), "{folder}")' in text("web/e2e/run.spec.ts")
    tsconfig = text("web/tsconfig.json")  # TypeScript's JSON allows comments and trailing commas
    assert f'"{folder}/types/**/*.ts"' in tsconfig and f'"{folder}/dev/types/**/*.ts"' in tsconfig
    assert f"/web/{folder}/" in text(".gitignore").splitlines()
