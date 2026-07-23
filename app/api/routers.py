"""Регистрация роутеров API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints.directory import directory_router
from app.api.endpoints.health import health_router
from app.api.endpoints.parsing import parsing_router

main_router = APIRouter(prefix="/api")
main_router.include_router(health_router, tags=["Health"])
main_router.include_router(directory_router, tags=["Directory"])
main_router.include_router(parsing_router, tags=["Parsing"])
