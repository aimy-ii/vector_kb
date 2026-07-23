"""Точка входа FastAPI-приложения."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routers import main_router
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)
app.include_router(main_router)
