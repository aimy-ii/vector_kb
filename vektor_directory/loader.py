"""Загрузка JSON городов пакета справочника.

Данные лежат внутри пакета (`vektor_directory/data`) и читаются через
`importlib.resources`, поэтому работают и из исходников, и после установки колеса.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from importlib import resources
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load() -> dict[str, dict[str, Any]]:
    """Читает все города пакета в память. Кэшируется на процесс.

    Возвращает:
        Словарь «слаг города → урезанный файл города».
        Битый файл пропускается с записью в лог.
    """
    cities: dict[str, dict[str, Any]] = {}
    data_root = resources.files("vektor_directory").joinpath("data")
    for entry in sorted(data_root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith("_") or not entry.name.endswith(".json"):
            continue
        try:
            payload = entry.read_text(encoding="utf-8")
            city = json.loads(payload)
            slug = city["meta"]["city_slug"]
            cities[slug] = city
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("Пропускаю битый файл справочника: %s", entry.name)
    return cities
