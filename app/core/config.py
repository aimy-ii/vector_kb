"""Настройки приложения из переменных окружения."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Параметры сервиса. Секретов нет — сервис во внутренней сети."""

    app_title: str = "Vector KB"
    app_version: str = "0.1.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8317
    log_level: str = "INFO"

    raw_dir: Path = Path("data/raw")
    out_dir: Path = Path("data/out")
    directory_data_dir: Path = Path("app/services/directory_service/data")
    index_path: Path = Path("data/index.json")
    landmarks_path: Path = Path("app/services/parsing_service/landmarks.json")

    parse_pause: float = 1.5
    request_timeout: float = 30.0

    geocoder_contact: str = ""
    geocoder_timeout: float = 5.0
    geocoder_pause: float = 1.1
    dadata_api_key: str = ""
    dadata_secret_key: str = ""
    geocoder_provider: str = "dadata"
    nearest_radius_km: float = 50.0
    nearest_limit: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def geocoder_user_agent(self) -> str:
        """
        Собирает User-Agent для геокодера.

        Nominatim требует реальный способ связи и блокирует запросы с
        фиктивными контактами вроде example.org. Значение берётся из
        переменной окружения GEOCODER_CONTACT.

        Возвращает:
            Строку User-Agent с указанным контактом.
        """
        return f"vector-kb/0.1 ({self.geocoder_contact})"


settings = Settings()
