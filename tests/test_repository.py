"""Ciò che serve a costruire e provare il progetto è versionato: un clone pulito ha tutto il codice.

Il 2026-11-03 la regola `projects/` di .gitignore, scritta per i materiali del cliente, nascondeva le pagine
del cruscotto in `web/src/app/projects/`: le prove passavano perché i file erano sul disco, ma il commit non
li aveva.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from agency.config import REPO_ROOT

SOURCES = ["src", "tests", "web/src", "web/e2e", "web/scripts", "docs", "registry", "schemas", "prompts"]
# Ciò che le prove e gli strumenti scrivono accanto ai sorgenti, e che si rigenera.
GENERATED = ("__pycache__/", ".pyc", "web/e2e/.data/", "web/e2e/.results/")


def ignored(paths: list[str]) -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [path for path in listed if not any(part in path for part in GENERATED)]


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(), reason="serve un clone git"
)
def test_no_source_file_is_hidden_by_gitignore() -> None:
    assert ignored(SOURCES) == []


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(), reason="serve un clone git"
)
def test_the_client_materials_stay_out_of_git() -> None:
    """L'eccezione per le pagine non apre la cartella dei progetti del cliente."""
    result = subprocess.run(
        ["git", "check-ignore", "projects/merlo/brief.md", "web/projects/x.svg", "src/projects/x.svg"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.splitlines() == [
        "projects/merlo/brief.md",
        "web/projects/x.svg",
        "src/projects/x.svg",
    ]
