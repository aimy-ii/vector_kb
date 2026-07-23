"""Эндпоинты живости сервиса и перечитывания справочника."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import HealthResponse, ReloadResponse
from app.services.directory_service import api as directory_api

health_router = APIRouter()


@health_router.get(
    path="/health",
    summary="Живость сервиса и снимок справочника",
    response_model=HealthResponse,
)
async def get_health() -> HealthResponse:
    """Возвращает статус и число городов/филиалов в памяти."""
    return directory_api.health()


@health_router.post(
    path="/reload",
    summary="Перечитать справочник с диска",
    response_model=ReloadResponse,
)
async def post_reload() -> ReloadResponse:
    """Перечитывает JSON городов в память без перезапуска процесса."""
    return directory_api.reload_directory()
