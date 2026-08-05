"""Геокодер на Nominatim (OpenStreetMap) через geopy.

Nominatim бесплатен и не требует ключа, но ограничивает частоту запросов —
подходит для отладки и небольших объёмов. Смена провайдера сводится к замене
класса в `geocoders/__init__.py`: в geopy есть, в частности, Yandex.

Клиент geopy синхронный, поэтому вызов уходит в отдельный поток через
`asyncio.to_thread` — цикл событий не блокируется, дополнительный HTTP-клиент
в зависимости не тащится.

На нераспознанном запросе Nominatim может вернуть область или регион целиком.
Такой результат отбраковывается по размеру рамки: район города укладывается в
доли градуса, регион занимает несколько. Отличать по типу объекта нельзя —
район города приходит как `administrative` и является нормальным ответом.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from geopy.exc import GeocoderInsufficientPrivileges, GeocoderServiceError
from geopy.geocoders import Nominatim

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BBOX_DEGREES = 1.0


def is_too_coarse(raw: dict[str, Any]) -> bool:
    """
    Проверяет, не вернул ли геокодер слишком крупный объект.

    Аргументы:
        raw: сырой ответ провайдера (поле `raw` объекта Location).

    Возвращает:
        True, если рамка объекта шире допустимой и точку использовать нельзя.
    """
    box = raw.get("boundingbox")
    if not isinstance(box, list) or len(box) != 4:
        return False
    try:
        south, north, west, east = (float(value) for value in box)
    except (TypeError, ValueError):
        return False
    return (north - south) > MAX_BBOX_DEGREES or (east - west) > MAX_BBOX_DEGREES


class NominatimGeocoder:
    """Геокодер поверх Nominatim.

    Nominatim не предназначен для систематической нагрузки: на боевом потоке
    звонков провайдера нужно менять (см. `geocoders/__init__.py`).
    """

    def __init__(self) -> None:
        """Создаёт клиент с User-Agent и таймаутом из настроек."""
        if not settings.geocoder_contact.strip():
            raise RuntimeError(
                "Не задан GEOCODER_CONTACT: Nominatim блокирует запросы без "
                "реального способа связи. Укажите рабочий e-mail или адрес "
                "сайта в переменной окружения GEOCODER_CONTACT."
            )
        self._client = Nominatim(
            user_agent=settings.geocoder_user_agent,
            timeout=settings.geocoder_timeout,
        )

    def geocode_sync(self, text: str) -> tuple[float, float] | None:
        """
        Синхронно переводит описание места в координаты.

        Используется скриптом разовой простановки координат.

        Аргументы:
            text: строка запроса, например «Купчино, Санкт-Петербург».

        Возвращает:
            Пару (широта, долгота) либо None, если место не распознано,
            оказалось слишком крупным объектом или провайдер не ответил.
        """
        try:
            location = self._client.geocode(text, exactly_one=True, country_codes="ru")
        except GeocoderInsufficientPrivileges:
            logger.exception(
                "[GEOCODER] Провайдер отклонил запрос (недостаточно прав): %r. "
                "Проверьте GEOCODER_CONTACT и политику использования Nominatim.",
                text,
            )
            return None
        except GeocoderServiceError:
            logger.exception("[GEOCODER] Запрос не удался: %r", text)
            return None

        if location is None:
            logger.info("[GEOCODER] Место не найдено: %r", text)
            return None
        if is_too_coarse(location.raw):
            logger.info("[GEOCODER] Объект слишком крупный, отброшен: %r", text)
            return None
        return float(location.latitude), float(location.longitude)

    async def geocode(self, text: str) -> tuple[float, float] | None:
        """
        Переводит описание места в координаты, не блокируя цикл событий.

        Аргументы:
            text: строка запроса.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return await asyncio.to_thread(self.geocode_sync, text)
