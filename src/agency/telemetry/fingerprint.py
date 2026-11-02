"""Prende l'impronta di un'esecuzione dai file del repository e dalle CLI installate.

Le CLI si interrogano solo con `--version`, come fa già l'indice dei comandi Craft: sono quelle di
`docs/04-TOOLS.md`, mai programmi sconosciuti. Ricevono solo `PATH`: la chiave API non esce dal gateway.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from functools import cache
from pathlib import Path

from agency.config import REPO_ROOT, Settings
from agency.contracts.run import Fingerprint

TOOLS = ("vectorcraft-cli", "effectcraft-cli", "photocraft-cli", "figcraft-cli", "blender")
VERSION_SECONDS = 30


@cache
def version(binary: str) -> str:
    """La prima riga di `--version`. Una CLI non cambia mentre il processo lavora: si chiede una volta."""
    if shutil.which(binary) is None:
        return "assente"
    try:
        done = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=VERSION_SECONDS,
            check=False,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.SubprocessError):
        return "non risponde"
    lines = done.stdout.strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else "non risponde"


def _hashes(root: Path, folder: str) -> dict[str, str]:
    files = sorted(
        path for path in (root / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts
    )
    return {path.relative_to(root).as_posix(): _sha256(path) for path in files}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def take(
    settings: Settings,
    model: str,
    effort: str,
    root: Path = REPO_ROOT,
    tools: tuple[str, ...] = TOOLS,
) -> Fingerprint:
    """`model` ed `effort` sono le scelte del cliente, salvate nel progetto."""
    return Fingerprint(
        model=model,
        effort=effort,
        explorer_effort=settings.explorer_effort,
        proposal_effort=settings.proposal_effort,
        explorers=settings.explorers,
        max_parallel=settings.max_parallel,
        prompts=_hashes(root, "prompts"),
        registry=_hashes(root, "registry"),
        code=_hashes(root, "src/agency"),
        lock=_sha256(root / "uv.lock"),
        python=platform.python_version(),
        tools={binary: version(binary) for binary in tools},
    )
