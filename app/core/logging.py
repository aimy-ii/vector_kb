"""Настройка логирования до создания FastAPI-приложения."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Конфигурирует корневой логгер по уровню из настроек."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
