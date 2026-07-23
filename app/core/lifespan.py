"""Прогрев справочника при старте и освобождение при остановке."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services.directory_service import directory_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Загружает справочник в память при старте приложения."""
    count = directory_store.load()
    logger.info("[LIFESPAN] Справочник прогрет, городов=%s", count)
    yield
