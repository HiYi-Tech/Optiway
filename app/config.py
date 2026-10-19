from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["auto", "google", "osrm", "local"]


class Settings(BaseSettings):
    """Runtime settings, loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Optiway"
    ROUTE_PROVIDER: ProviderName = "auto"
    GOOGLE_MAPS_API_KEY: str | None = None
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    HTTP_TIMEOUT_SECONDS: float = 15.0
    MAX_INTERMEDIATES: int = 10
    MAP_TILE_URL: str = "https://tile.openstreetmap.de/{z}/{x}/{y}.png"
    MAP_TILE_ATTRIBUTION: str = (
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    )
    MAP_TILE_MAX_ZOOM: int = 19

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_MAPS_API_KEY and self.GOOGLE_MAPS_API_KEY.strip())


settings = Settings()
