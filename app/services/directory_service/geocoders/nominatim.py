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

    def build_query(self, address: str, city: str | None) -> str:
        """
        Собирает строку запроса из адреса и города.

        Аргументы:
            address: нормализованный адрес филиала.
            city: название города или None, если адрес уже содержит свой.

        Возвращает:
            Строку в порядке, который правильно разбирает этот провайдер.
        """
        if city is None:
            return address
        return f"{address}, {city}"

    def geocode_sync(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Синхронно переводит описание места в координаты.

        Используется скриптом разовой простановки координат.

        Аргументы:
            text: строка запроса, например «Купчино, Санкт-Петербург».
            city: город для ограничения поиска; Nominatim его игнорирует.

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

    def geocode_city_center_sync(self, city_name: str) -> tuple[float, float] | None:
        """
        Геокодирует центр города для ``meta.lat``/``meta.lon``.

        Для центра города крупная рамка допустима — отбраковка ``is_too_coarse``
        не применяется. Неоднозначные названия уточняются подсказками DaData.

        Аргументы:
            city_name: название города из меты файла.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        from app.services.directory_service.geocoders.dadata import CITY_CENTER_HINTS

        query = CITY_CENTER_HINTS.get(city_name, city_name)
        try:
            location = self._client.geocode(query, exactly_one=True, country_codes="ru")
        except GeocoderInsufficientPrivileges:
            logger.exception(
                "[GEOCODER] Провайдер отклонил запрос центра города: %r",
                query,
            )
            return None
        except GeocoderServiceError:
            logger.exception("[GEOCODER] Запрос центра города не удался: %r", query)
            return None
        if location is None:
            logger.info("[GEOCODER] Центр города не найден: %r", query)
            return None
        return float(location.latitude), float(location.longitude)

    async def geocode(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Переводит описание места в координаты, не блокируя цикл событий.

        Аргументы:
            text: строка запроса.
            city: город для ограничения поиска; Nominatim его игнорирует.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return await asyncio.to_thread(self.geocode_sync, text, city)
