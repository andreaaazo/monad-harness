"""Configurazione da ambiente o `.env`. La chiave API non viene mai stampata né registrata."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agency.contracts.layout import CHECKOUT, DataLayout, data_root, projects_root

REPO_ROOT = CHECKOUT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=CHECKOUT / ".env", env_prefix="AGENCY_", extra="ignore")

    data_dir: Path = Field(default_factory=data_root)
    projects_dir: Path = Field(default_factory=projects_root)
    explorer_effort: str = "high"
    proposal_effort: str = "high"
    explorers: int = 5
    max_parallel: int = 5
    toolchain_dir: Path = Path.home() / ".local/share/design-agency"
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "AGENCY_ANTHROPIC_API_KEY")
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def _absolute_data_dir(cls, value: object) -> Path:
        """The value from the environment, `.env` or the caller, checked by the resolver the server uses."""
        return data_root({"AGENCY_DATA_DIR": str(value)})

    @field_validator("projects_dir", mode="before")
    @classmethod
    def _absolute_projects_dir(cls, value: object) -> Path:
        return projects_root({"AGENCY_PROJECTS_DIR": str(value)})

    @property
    def layout(self) -> DataLayout:
        return DataLayout(self.data_dir)

    @property
    def ledger_path(self) -> Path:
        return self.layout.ledger

    @property
    def checkpoints_path(self) -> Path:
        return self.layout.checkpoints

    @property
    def artifacts_dir(self) -> Path:
        return self.layout.artifacts

    @property
    def traces_path(self) -> Path:
        return self.layout.traces

    @property
    def insights_path(self) -> Path:
        return self.layout.insights

    def project_dir(self, slug: str) -> Path:
        return (self.projects_dir / slug).resolve()
