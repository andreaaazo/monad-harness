"""Configurazione da ambiente o `.env`. La chiave API non viene mai stampata né registrata."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENCY_", extra="ignore")

    data_dir: Path = Path(".data")
    projects_dir: Path = Path("projects")
    project_budget_usd: float = 25.0
    explorer_effort: str = "high"
    proposal_effort: str = "high"
    explorers: int = 5
    max_parallel: int = 5
    toolchain_dir: Path = Path.home() / ".local/share/design-agency"
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")
    )

    @property
    def ledger_path(self) -> Path:
        return self.data_dir / "ledger.sqlite"

    @property
    def checkpoints_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    def project_dir(self, slug: str) -> Path:
        return (self.projects_dir / slug).resolve()
