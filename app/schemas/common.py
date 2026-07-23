"""Общие схемы ответов."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Живость сервиса и снимок загруженного справочника."""

    status: str = Field(title="Статус")
    cities_count: int = Field(title="Число городов")
    branches_count: int = Field(title="Число филиалов")
    loaded_at: datetime | None = Field(default=None, title="Время последней загрузки")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "cities_count": 41,
                "branches_count": 120,
                "loaded_at": "2026-07-23T10:00:00Z",
            }
        }
    )


class ReloadResponse(BaseModel):
    """Результат перечитывания справочника с диска."""

    cities_count: int = Field(title="Число загруженных городов")
    branches_count: int = Field(title="Число загруженных филиалов")
    loaded_at: datetime | None = Field(default=None, title="Время загрузки")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cities_count": 41,
                "branches_count": 120,
                "loaded_at": "2026-07-23T10:05:00Z",
            }
        }
    )
