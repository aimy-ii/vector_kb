"""Схемы фоновых задач парсинга."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants.parsing import JobStatus


class ParseRequest(BaseModel):
    """Параметры запуска обновления данных."""

    only: list[str] | None = Field(
        default=None, title="Слаги городов", description="Если заданы — обход только их"
    )
    force: bool = Field(default=False, title="Игнорировать кэш страниц")
    include_external: bool = Field(default=False, title="Включая города на чужих доменах")
    include_done: bool = Field(
        default=False,
        title="Пересобирать города, собранные вручную",
        description=(
            "По умолчанию выключено: Санкт-Петербург, Екатеринбург и Пермь "
            "выверены вручную, пересборка с сайта перезапишет эти данные"
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "only": ["omsk", "krasnoyarsk"],
                "force": False,
                "include_external": False,
                "include_done": False,
            }
        }
    )


class ParseJobAccepted(BaseModel):
    """Ответ на успешный запуск задачи."""

    job_id: str = Field(title="Идентификатор задачи")
    status: JobStatus = Field(title="Статус")

    model_config = ConfigDict(
        json_schema_extra={"example": {"job_id": "a1b2c3d4", "status": "pending"}}
    )


class ParseJobStatus(BaseModel):
    """Состояние фоновой задачи парсинга."""

    job_id: str = Field(title="Идентификатор задачи")
    status: JobStatus = Field(title="Статус")
    started_at: datetime | None = Field(default=None, title="Время старта")
    finished_at: datetime | None = Field(default=None, title="Время окончания")
    step: str | None = Field(default=None, title="Текущий шаг")
    cities_processed: int = Field(default=0, title="Обработано городов")
    error: str | None = Field(default=None, title="Текст ошибки")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "a1b2c3d4",
                "status": "running",
                "started_at": "2026-07-23T10:00:00Z",
                "finished_at": None,
                "step": "fetch",
                "cities_processed": 12,
                "error": None,
            }
        }
    )


class ParseConflict(BaseModel):
    """Ответ при попытке запустить вторую задачу параллельно."""

    detail: str = Field(title="Сообщение")
    job_id: str = Field(title="Идентификатор активной задачи")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Уже выполняется задача парсинга",
                "job_id": "a1b2c3d4",
            }
        }
    )
