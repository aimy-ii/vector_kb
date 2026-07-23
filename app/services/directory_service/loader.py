"""Загрузка JSON городов справочника с диска или из пакета.

Данные лежат в `directory_service/data` и читаются либо с пути из настроек,
либо через `importlib.resources`, чтобы работало после установки колеса.
"""

from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_from_path(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Читает все JSON городов из каталога на диске."""
    cities: dict[str, dict[str, Any]] = {}
    if not data_dir.is_dir():
        logger.warning("[DIRECTORY] Каталог данных не найден: %s", data_dir)
        return cities
    for path in sorted(data_dir.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        try:
            city = json.loads(path.read_text(encoding="utf-8"))
            slug = city["meta"]["city_slug"]
            cities[slug] = city
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("[DIRECTORY] Пропускаю битый файл: %s", path.name)
    return cities


def _load_from_package() -> dict[str, dict[str, Any]]:
    """Читает JSON городов из данных пакета через importlib.resources."""
    cities: dict[str, dict[str, Any]] = {}
    data_root = resources.files("app.services.directory_service").joinpath("data")
    for entry in sorted(data_root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith("_") or not entry.name.endswith(".json"):
            continue
        try:
            payload = entry.read_text(encoding="utf-8")
            city = json.loads(payload)
            slug = city["meta"]["city_slug"]
            cities[slug] = city
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("[DIRECTORY] Пропускаю битый файл пакета: %s", entry.name)
    return cities


def load_cities(data_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """
    Загружает города справочника.

    Args:
        data_dir: каталог на диске. Если None или каталог пуст/отсутствует —
            читает встроенные данные пакета.

    Returns:
        Словарь «слаг города → урезанный файл города».
    """
    if data_dir is not None:
        cities = _load_from_path(data_dir)
        if cities:
            return cities
    return _load_from_package()
