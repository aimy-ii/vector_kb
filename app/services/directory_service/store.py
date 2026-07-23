"""Хранилище справочника в памяти процесса."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.directory_service.loader import load_cities

logger = logging.getLogger(__name__)


class DirectoryStore:
    """Держит загруженные города в памяти и умеет перечитывать их с диска.

    Обработка HTTP-запросов читает только из памяти — обращений к диску нет.
    """

    def __init__(self) -> None:
        self._cities: dict[str, dict[str, Any]] = {}
        self._loaded_at: datetime | None = None

    @property
    def cities(self) -> dict[str, dict[str, Any]]:
        """Загруженные города: слаг → урезанный JSON."""
        return self._cities

    @property
    def loaded_at(self) -> datetime | None:
        """Время последней успешной загрузки."""
        return self._loaded_at

    @property
    def cities_count(self) -> int:
        """Число городов в памяти."""
        return len(self._cities)

    @property
    def branches_count(self) -> int:
        """Число филиалов во всех городах."""
        return sum(len(city["branches"]["items"]) for city in self._cities.values())

    def load(self, data_dir: Path | None = None) -> int:
        """
        Читает файлы справочника в память.

        Args:
            data_dir: каталог с JSON городов; по умолчанию из настроек.

        Returns:
            Число загруженных городов.
        """
        path = data_dir if data_dir is not None else settings.directory_data_dir
        self._cities = load_cities(data_dir=path)
        self._loaded_at = datetime.now(UTC)
        logger.info(
            "[DIRECTORY] Загружено городов=%s филиалов=%s из %s",
            self.cities_count,
            self.branches_count,
            path,
        )
        return self.cities_count

    def reload(self, data_dir: Path | None = None) -> int:
        """Перечитывает файлы в память без перезапуска процесса."""
        return self.load(data_dir=data_dir)


directory_store = DirectoryStore()
