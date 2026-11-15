"""A read-only check of the environment. It asks only known CLIs, never unknown launchers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agency.config import REPO_ROOT, Settings
from agency.workshop.sandbox import MEMORY_MAX_BYTES, TASKS_MAX, scope_problem

BINARIES: tuple[tuple[str, bool, str], ...] = (
    ("vectorcraft-cli", True, "master vettoriali e tavola del giudizio"),
    ("effectcraft-cli", True, "master motion"),
    ("figcraft-cli", True, "master di interfaccia"),
    ("photocraft-cli", True, "master immagine"),
    ("blender", True, "master 3D"),
    ("ffmpeg", True, "frame e video"),
    ("ffprobe", True, "metadati video"),
    ("gs", True, "preflight PDF"),
    ("bwrap", True, "sandbox degli strumenti"),
    ("fc-match", True, "font della presentazione"),
    ("docker", False, "il cruscotto in Docker, task docker:up (ADR-0040)"),
    ("nvidia-smi", False, "GPU per Blender, SigLIP e ComfyUI"),
)

WEB = REPO_ROOT / "web"
# The command docs/04-TOOLS.md gives Andrea for Playwright's browser.
CHROMIUM_INSTALL = "mise exec -- pnpm --dir web exec playwright install chromium"


@dataclass(frozen=True)
class Finding:
    """One line of `agency doctor`: what is checked, whether it is there, whether it is required, and why."""

    name: str
    ok: bool
    required: bool
    detail: str


def _gpu() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "non rilevata"
    return result.stdout.strip()


def _package(start: Path, name: str) -> Path | None:
    """`name` as Node resolves it from the package at `start`: in the node_modules of each folder above it.

    pnpm links each package into its own folder, so the links are followed at every step."""
    real = start.resolve()
    for folder in (real, *real.parents):
        candidate = folder / "node_modules" / name
        if folder.name != "node_modules" and candidate.is_dir():
            return candidate.resolve()
    return None


def _expected_browsers() -> tuple[Path, list[str]] | None:
    """The browser folder Playwright reads, and the Chromium folders its installed version expects there.

    None when web/node_modules is not installed yet. It reads browsers.json and runs nothing."""
    test = _package(WEB, "@playwright/test")
    playwright = _package(test, "playwright") if test else None
    core = _package(playwright, "playwright-core") if playwright else None
    if core is None:
        return None
    browsers = json.loads((core / "browsers.json").read_text(encoding="utf-8"))["browsers"]
    wanted = [b for b in browsers if b["name"] in ("chromium", "chromium-headless-shell")]
    folders = [f"{b['name'].replace('-', '_')}-{b['revision']}" for b in wanted]
    custom = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if custom == "0":
        return core / ".local-browsers", folders
    if custom:
        return Path(custom), folders
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "ms-playwright", folders


def _chromium() -> Finding:
    """Playwright's Chromium, at the revision the installed playwright-core expects: `task check` needs it."""
    expected = _expected_browsers()
    if expected is None:
        return Finding("Chromium", False, True, "web/node_modules manca: esegui task setup")
    root, folders = expected
    missing = [folder for folder in folders if not (root / folder).is_dir()]
    if missing:
        return Finding(
            "Chromium", False, True, f"manca {', '.join(missing)} per le prove: {CHROMIUM_INSTALL}"
        )
    return Finding("Chromium", True, True, f"{', '.join(folders)} per le prove Playwright")


def run_checks(settings: Settings | None = None) -> list[Finding]:
    """The machine's findings, read-only: known CLIs, Chromium, the API key, the sandbox caps and the GPU."""
    settings = settings or Settings()
    findings = [
        Finding(name, shutil.which(name) is not None, required, why) for name, required, why in BINARIES
    ]
    findings.append(_chromium())
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY")) or settings.anthropic_api_key is not None
    findings.append(Finding("chiave API", has_key, False, "serve da M1, non per i test locali"))
    why = scope_problem()
    caps = f"scope systemd con {MEMORY_MAX_BYTES // 2**30} GiB di memoria e {TASKS_MAX} task"
    findings.append(Finding("limiti sandbox", why is None, True, caps if why is None else why))
    findings.append(Finding("GPU", shutil.which("nvidia-smi") is not None, False, _gpu()))
    return findings
