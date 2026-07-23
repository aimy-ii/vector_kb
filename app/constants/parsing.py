"""Константы пайплайна сбора данных."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Статус фоновой задачи парсинга."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


DEFAULT_PARSE_PAUSE = 1.5
"""Пауза между городами при сборе, секунд."""

DEFAULT_REQUEST_TIMEOUT = 30.0
"""Таймаут HTTP-запроса к сайту, секунд."""

PARSE_LOG_PREFIX = "[PARSING]"
"""Устойчивый префикс логов пайплайна."""
