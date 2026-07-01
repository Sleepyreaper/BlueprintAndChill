from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="BlueprintAndChill", alias="BLUEPRINTANDCHILL_APP_NAME")
    environment: str = Field(default="development", alias="BLUEPRINTANDCHILL_ENV")
    debug: bool = Field(default=False, alias="BLUEPRINTANDCHILL_DEBUG")
    host: str = Field(default="0.0.0.0", alias="BLUEPRINTANDCHILL_HOST")
    port: int = Field(default=8000, alias="BLUEPRINTANDCHILL_PORT")
    request_data_dir: Path = Field(
        default=Path("local_data/requests"), alias="BLUEPRINTANDCHILL_REQUEST_DATA_DIR"
    )

    entra_tenant_id: str | None = Field(default=None, alias="BLUEPRINTANDCHILL_ENTRA_TENANT_ID")
    entra_client_id: str | None = Field(default=None, alias="BLUEPRINTANDCHILL_ENTRA_CLIENT_ID")
    entra_client_secret: str | None = Field(
        default=None, alias="BLUEPRINTANDCHILL_ENTRA_CLIENT_SECRET"
    )
    entra_authority: str = Field(
        default="https://login.microsoftonline.com",
        alias="BLUEPRINTANDCHILL_ENTRA_AUTHORITY",
    )
    entra_redirect_path: str = Field(
        default="/auth/callback", alias="BLUEPRINTANDCHILL_ENTRA_REDIRECT_PATH"
    )
    entra_scopes: str = Field(default="openid,profile,email", alias="BLUEPRINTANDCHILL_ENTRA_SCOPES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def template_dir(self) -> Path:
        return Path(__file__).parent / "web" / "templates"

    @property
    def static_dir(self) -> Path:
        return Path(__file__).parent / "web" / "static"

    @property
    def is_entra_configured(self) -> bool:
        return bool(self.entra_tenant_id and self.entra_client_id)

    @property
    def entra_scopes_list(self) -> list[str]:
        return [scope.strip() for scope in self.entra_scopes.split(",") if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
