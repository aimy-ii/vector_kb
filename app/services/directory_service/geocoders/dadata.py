"""Геокодер на DaData (стандартизация адресов по ФИАС).

DaData опирается на официальный реестр адресов России и лучше Nominatim
разбирает дробные номера домов, корпуса и длинные названия улиц. Бесплатный
лимит — 10 000 запросов в сутки. Ключи API берутся из переменных окружения
``DADATA_API_KEY`` и ``DADATA_SECRET_KEY``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLEAN_ADDRESS_URL = "https://cleaner.dadata.ru/api/v1/clean/address"

# qc_geo > 2 — точка уровня населённого пункта или города; для подбора
# ближайшего филиала такая точность бесполезна (0 дом, 1 ближайший дом, 2 улица).
MAX_ACCEPTABLE_QC_GEO = 2


class DadataGeocoder:
    """Клиент API стандартизации адресов DaData."""

    def __init__(self) -> None:
        """Создаёт клиент; оба ключа должны быть заданы в окружении."""
        api_key = settings.dadata_api_key.strip()
        secret_key = settings.dadata_secret_key.strip()
        if not api_key or not secret_key:
            raise RuntimeError(
                "Не заданы ключи DaData. Укажите переменные окружения "
                "DADATA_API_KEY и DADATA_SECRET_KEY."
            )
        self._api_key = api_key
        self._secret_key = secret_key
        self._timeout = settings.geocoder_timeout
        #: Точность последнего успешного ответа (поле qc_geo), иначе None.
        self.last_qc_geo: int | None = None

    def _headers(self) -> dict[str, str]:
        """Собирает заголовки авторизации и JSON."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self._api_key}",
            "X-Secret": self._secret_key,
        }

    def geocode_sync(self, text: str) -> tuple[float, float] | None:
        """
        Синхронно переводит адрес в координаты через DaData Cleaner.

        Аргументы:
            text: строка адреса, например «Невский проспект, 28, Санкт-Петербург».

        Возвращает:
            Пару (широта, долгота) либо None, если адрес не распознан,
            точность слишком грубая или провайдер не ответил.
        """
        self.last_qc_geo = None
        try:
            response = httpx.post(
                CLEAN_ADDRESS_URL,
                json=[text],
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            logger.exception("[GEOCODER] Сетевая ошибка DaData: %r", text)
            return None

        if response.status_code in (401, 403):
            logger.error(
                "[GEOCODER] DaData не приняла ключи (HTTP %s). "
                "Проверьте DADATA_API_KEY и DADATA_SECRET_KEY.",
                response.status_code,
            )
            return None
        if response.status_code == 429:
            logger.error("[GEOCODER] Исчерпан дневной лимит запросов DaData (HTTP 429).")
            return None
        if response.status_code >= 400:
            logger.error(
                "[GEOCODER] DaData вернула HTTP %s для запроса %r",
                response.status_code,
                text,
            )
            return None

        try:
            payload: Any = response.json()
        except ValueError:
            logger.exception("[GEOCODER] Некорректный JSON от DaData: %r", text)
            return None

        return self._parse_payload(payload, text)

    def _parse_payload(self, payload: Any, text: str) -> tuple[float, float] | None:
        """
        Разбирает JSON-ответ Cleaner API.

        Аргументы:
            payload: разобранный JSON (ожидается массив объектов).
            text: исходный запрос — для логов.

        Возвращает:
            Координаты либо None.
        """
        if not isinstance(payload, list) or not payload:
            logger.info("[GEOCODER] DaData: пустой ответ на %r", text)
            return None

        item = payload[0]
        if not isinstance(item, dict):
            logger.info("[GEOCODER] DaData: неожиданный формат ответа на %r", text)
            return None

        qc_geo = item.get("qc_geo")
        try:
            qc_geo_int = int(qc_geo) if qc_geo is not None else None
        except (TypeError, ValueError):
            qc_geo_int = None

        if qc_geo_int is None or qc_geo_int > MAX_ACCEPTABLE_QC_GEO:
            logger.info(
                "[GEOCODER] DaData: qc_geo=%r слишком грубый для %r",
                qc_geo,
                text,
            )
            return None

        geo_lat = item.get("geo_lat")
        geo_lon = item.get("geo_lon")
        if geo_lat is None or geo_lon is None:
            logger.info("[GEOCODER] DaData: нет координат для %r", text)
            return None

        try:
            lat = float(geo_lat)
            lon = float(geo_lon)
        except (TypeError, ValueError):
            logger.info(
                "[GEOCODER] DaData: нечисловые координаты для %r: %r, %r",
                text,
                geo_lat,
                geo_lon,
            )
            return None

        self.last_qc_geo = qc_geo_int
        return lat, lon

    async def geocode(self, text: str) -> tuple[float, float] | None:
        """
        Переводит адрес в координаты, не блокируя цикл событий.

        Аргументы:
            text: строка адреса.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return await asyncio.to_thread(self.geocode_sync, text)
