"""Dove stanno i dati in `.data/`: un solo proprietario, per il motore che scrive e per chi legge.

Il server del cruscotto lo usa senza passare da `agency.config`, che legge `.env` e quindi la chiave API.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from agency.contracts.project import ProjectName

# The checkout the code runs from: `prompts/`, `registry/`, `.env` and the default data root hang from it,
# whatever the current folder (ADR-0045). Each worktree is its own checkout, with its own `.data`.
CHECKOUT = Path(__file__).resolve().parents[3]


class RelativeDataRoot(Exception):
    """A data or projects folder given as a relative path: it would follow the current folder (ADR-0045)."""

    def __init__(self, name: str, value: str) -> None:
        self.name, self.value = name, value
        super().__init__(
            f"{name} deve essere un percorso assoluto, non {value!r}: uno relativo dipende dalla cartella"
            " da cui parte il comando"
        )


def data_root(environ: Mapping[str, str] = os.environ) -> Path:
    """The registry's folder: `AGENCY_DATA_DIR`, which must be absolute, or `.data` in the checkout.

    The engine and the dashboard server both resolve it here, so the two never look at different registries.
    """
    return _anchored(environ, "AGENCY_DATA_DIR", CHECKOUT / ".data")


def projects_root(environ: Mapping[str, str] = os.environ) -> Path:
    """The client projects' folder, by the same rule: `AGENCY_PROJECTS_DIR`, or `projects` in the checkout."""
    return _anchored(environ, "AGENCY_PROJECTS_DIR", CHECKOUT / "projects")


def projection_root(environ: Mapping[str, str] = os.environ) -> Path | None:
    """Where the projection lives if not beside the registry: `AGENCY_PROJECTION_DIR`, which must be absolute.

    None without the variable: the projection then follows whatever the registry's folder is when it is used.
    """
    return _anchored(environ, "AGENCY_PROJECTION_DIR", None)


def _anchored[Default: (Path, None)](
    environ: Mapping[str, str], name: str, default: Default
) -> Path | Default:
    value = environ.get(name)
    if value is None:
        return default
    if not Path(value).is_absolute():
        raise RelativeDataRoot(name, value)
    return Path(value)


@dataclass(frozen=True)
class DataLayout:
    """`projection` è dove sta la proiezione di insights, se non accanto al registro. In Docker sta in
    memoria, e il container non aggiunge file al registro (ADR-0040)."""

    root: Path
    projection: Path | None = None

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.sqlite"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints.sqlite"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def traces(self) -> Path:
        return self.root / "traces.jsonl"

    @property
    def insights(self) -> Path:
        return (self.projection or self.root) / "insights.sqlite"

    @property
    def transcripts(self) -> Path:
        """Le trascrizioni delle istanze, una cartella per progetto."""
        return self.root / "runs"

    @property
    def locks(self) -> Path:
        """The folder of the project claims, one `<project>.lock` file each."""
        return self.root / "locks"

    def lock(self, project: str) -> Path:
        """The claim that lets one engine process at a time work on a project (COR-005)."""
        return self.locks / f"{project}.lock"

    def transcript(self, project: ProjectName, instance: str) -> Path:
        return self.transcripts / project / f"{instance}.jsonl"

    def cassette(self, project: ProjectName, run: int) -> Path:
        """The model's answers in one run started with `--record` (ADR-0048). Like `runs/`, it holds the
        client's materials, so it stays under the data root and is never versioned."""
        return self.root / "cassettes" / project / f"{run}.jsonl"

    def ops_inputs(self, project: str, instance: str) -> Path:
        """The files the harness writes for an instance's sandbox, bound read-only at /ops (ADR-0044)."""
        return self.ops_records(project, instance) / "in"

    def ops_records(self, project: str, instance: str) -> Path:
        """The harness's record of an instance's tool runs, read on resume. No sandbox sees it (ADR-0044)."""
        return self.root / "ops" / project / instance
