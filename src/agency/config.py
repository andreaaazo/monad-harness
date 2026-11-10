"""Configurazione da ambiente o `.env`. La chiave API non viene mai stampata né registrata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from agency.contracts.layout import CHECKOUT, DataLayout, RelativeDataRoot, data_root, projects_root
from agency.contracts.project import ProjectName

REPO_ROOT = CHECKOUT

# The only variables `.env` may hold, lowercased as the source reads them (ADR-0045).
_DOTENV_KEYS = ("anthropic_api_key", "agency_anthropic_api_key")


class DotenvHoldsSetting(Exception):
    """A setting in `.env`: only the engine reads that file, so the server would not see it (ADR-0045)."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"{name} è in .env, ma .env contiene solo la chiave API: mettilo nell'ambiente del processo,"
            " per esempio sulla riga di comando o nella shell"
        )


class _KeyOnlyDotEnv(DotEnvSettingsSource):
    """The `.env` source, which refuses any `AGENCY_*` line other than the API key."""

    def __call__(self) -> dict[str, Any]:
        for name in self.env_vars:  # file order, empty and bare lines included
            if name.startswith("agency_") and name not in _DOTENV_KEYS:
                raise DotenvHoldsSetting(name.upper())
        return super().__call__()


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        keyed = _KeyOnlyDotEnv(settings_cls, env_file=getattr(dotenv_settings, "env_file", None))
        return init_settings, env_settings, keyed, file_secret_settings

    @field_validator("data_dir", mode="before")
    @classmethod
    def _absolute_data_dir(cls, value: object) -> Path:
        """The value from the environment, `.env` or the caller, checked by the resolver the server uses."""
        return data_root({"AGENCY_DATA_DIR": str(value)})

    @field_validator("projects_dir", mode="before")
    @classmethod
    def _absolute_projects_dir(cls, value: object) -> Path:
        return projects_root({"AGENCY_PROJECTS_DIR": str(value)})

    @field_validator("toolchain_dir", mode="before")
    @classmethod
    def _absolute_toolchain_dir(cls, value: object) -> Path:
        """The sandbox binds this folder as given: a relative one would name a different folder per start."""
        if not Path(str(value)).is_absolute():
            raise RelativeDataRoot("AGENCY_TOOLCHAIN_DIR", str(value))
        return Path(str(value))

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

    def project_dir(self, slug: ProjectName) -> Path:
        return (self.projects_dir / slug).resolve()
