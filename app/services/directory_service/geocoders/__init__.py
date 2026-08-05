"""Выбор геокодера. Провайдер задаётся переменной окружения GEOCODER_PROVIDER."""

from __future__ import annotations

import functools
from typing import Any

from app.core.config import settings
from app.services.directory_service.geocoders.dadata import (
    DadataCleanerGeocoder,
    DadataSuggestionsGeocoder,
)
from app.services.directory_service.geocoders.nominatim import NominatimGeocoder

_PROVIDERS = {
    "dadata": DadataSuggestionsGeocoder,
    "dadata_cleaner": DadataCleanerGeocoder,
    "nominatim": NominatimGeocoder,
}


@functools.lru_cache(maxsize=1)
def build_geocoder() -> Any:
    """
    Создаёт геокодер согласно настройке GEOCODER_PROVIDER.

    Экземпляр кэшируется: повторные вызовы возвращают тот же объект.
    Кэш можно сбросить через ``build_geocoder.cache_clear()``.

    Возвращает:
        Экземпляр выбранного провайдера.

    Исключения:
        RuntimeError: указан неизвестный провайдер.
    """
    provider = settings.geocoder_provider.strip().lower()
    if provider not in _PROVIDERS:
        raise RuntimeError(
            f"Неизвестный GEOCODER_PROVIDER: {provider!r}. "
            f"Доступны: {', '.join(sorted(_PROVIDERS))}."
        )
    return _PROVIDERS[provider]()


class _LazyGeocoder:
    """Прокси: реальный клиент создаётся при первом вызове geocode."""

    def build_query(self, address: str, city: str | None) -> str:
        """Делегирует сборку строки запроса выбранному провайдеру."""
        return build_geocoder().build_query(address, city)

    def geocode_sync(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """Делегирует синхронный вызов выбранному провайдеру."""
        return build_geocoder().geocode_sync(text, city=city)

    async def geocode(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """Делегирует асинхронный вызов выбранному провайдеру."""
        return await build_geocoder().geocode(text, city=city)


geocoder = _LazyGeocoder()

__all__ = [
    "DadataCleanerGeocoder",
    "DadataSuggestionsGeocoder",
    "NominatimGeocoder",
    "build_geocoder",
    "geocoder",
]
