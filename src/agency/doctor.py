"""Verifica di sola lettura dell'ambiente. Interroga solo CLI note: mai launcher sconosciuti."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from agency.config import Settings

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
    ("docker", True, "Langfuse e ComfyUI"),
    ("nvidia-smi", False, "GPU per Blender, SigLIP e ComfyUI"),
)


@dataclass(frozen=True)
class Finding:
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


def run_checks(settings: Settings | None = None) -> list[Finding]:
    settings = settings or Settings()
    findings = [
        Finding(name, shutil.which(name) is not None, required, why) for name, required, why in BINARIES
    ]
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY")) or settings.anthropic_api_key is not None
    findings.append(Finding("chiave API", has_key, False, "serve da M1, non per i test locali"))
    findings.append(Finding("GPU", shutil.which("nvidia-smi") is not None, False, _gpu()))
    return findings
