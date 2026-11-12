"""What is needed to build and test the project is versioned: a clean clone has all the code.

On 2026-11-03 the `projects/` rule in .gitignore, written for the client's materials, hid the dashboard pages
in `web/src/app/projects/`: the tests passed because the files were on disk, but the commit did not have them.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from agency.config import REPO_ROOT

SOURCES = ["src", "tests", "web/src", "web/e2e", "web/scripts", "docs", "registry", "schemas", "prompts"]
# What the tests and the tools write beside the sources, and that is regenerated.
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
    """The exception for the pages does not open the folder of the client's projects."""
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
