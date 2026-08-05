"""Геокодеры DaData по базе ФИАС.

Два клиента с одним интерфейсом:

* ``DadataSuggestionsGeocoder`` — основной: API подсказок, бесплатный лимит
  10 000 запросов в сутки, нужен только ``DADATA_API_KEY``.
* ``DadataCleanerGeocoder`` — стандартизация (Cleaner): точнее на мусорных
  адресах, но бесплатно лишь 100 запросов, дальше платно; нужны оба ключа.

Координаты приходят в ``geo_lat``/``geo_lon``, точность — в ``qc_geo``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SUGGEST_ADDRESS_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
CLEAN_ADDRESS_URL = "https://cleaner.dadata.ru/api/v1/clean/address"

# qc_geo > 2 — точка уровня населённого пункта или города; для подбора
# ближайшего филиала такая точность бесполезна (0 дом, 1 ближайший дом, 2 улица).
MAX_ACCEPTABLE_QC_GEO = 2

#: Для центра города достаточно точности населённого пункта (qc_geo 3–4).
MAX_CITY_CENTER_QC_GEO = 4

#: Уточнения для неоднозначных названий при геокодировании центра города.
CITY_CENTER_HINTS: dict[str, str] = {
    "Адлер": "Адлерский район, Сочи",
    "Артём": "Артём, Приморский край",
    "Железногорск": "Железногорск, Красноярский край",
    "Иваново": "Иваново, Ивановская область",
    "Канск": "Канск, Красноярский край",
    "Тара": "Тара, Омская область",
}


def coords_from_dadata_item(
    item: dict[str, Any],
    text: str,
    *,
    max_qc_geo: int = MAX_ACCEPTABLE_QC_GEO,
) -> tuple[tuple[float, float], int] | None:
    """
    Достаёт координаты и qc_geo из объекта ответа DaData.

    Аргументы:
        item: словарь с полями ``geo_lat``, ``geo_lon``, ``qc_geo``.
        text: исходный запрос — для логов.
        max_qc_geo: максимальный допустимый ``qc_geo`` (для адресов — 2,
            для центра города допускается грубее).

    Возвращает:
        Кортеж ((широта, долгота), qc_geo) либо None, если поля пусты,
        нечисловые или точность слишком грубая.
    """
    qc_geo = item.get("qc_geo")
    try:
        qc_geo_int = int(qc_geo) if qc_geo is not None else None
    except (TypeError, ValueError):
        qc_geo_int = None

    if qc_geo_int is None or qc_geo_int > max_qc_geo:
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

    return (lat, lon), qc_geo_int


class _DadataBase:
    """Общая логика HTTP и разбора координат для клиентов DaData."""

    #: Имя сервиса в логах (подсказки / Cleaner).
    _service_label: str = "DaData"
    #: Подсказка, какие переменные проверить при 401/403.
    _auth_hint: str = "DADATA_API_KEY"

    def __init__(self, api_key: str) -> None:
        """Сохраняет API-ключ и таймаут из настроек."""
        self._api_key = api_key
        self._timeout = settings.geocoder_timeout
        #: Точность последнего успешного ответа (поле qc_geo), иначе None.
        self.last_qc_geo: int | None = None

    def _auth_headers(self) -> dict[str, str]:
        """Базовые JSON-заголовки с Token-авторизацией."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self._api_key}",
        }

    def _headers(self) -> dict[str, str]:
        """Заголовки запроса; подклассы могут добавить секрет."""
        return self._auth_headers()

    def _request_url(self) -> str:
        """URL эндпоинта DaData."""
        raise NotImplementedError

    def _request_body(self, text: str, city: str | None = None) -> Any:
        """Тело POST-запроса."""
        raise NotImplementedError

    def _extract_item(self, payload: Any, text: str) -> dict[str, Any] | None:
        """Достаёт из JSON объект с geo_lat/geo_lon/qc_geo."""
        raise NotImplementedError

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
        return f"{city}, {address}"

    def _handle_http_status(self, status_code: int, text: str) -> bool:
        """
        Обрабатывает неуспешный HTTP-статус.

        Аргументы:
            status_code: код ответа.
            text: исходный запрос — для логов.

        Возвращает:
            True, если статус ошибочный и вызов нужно прервать с None.
        """
        if status_code in (401, 403):
            logger.error(
                "[GEOCODER] %s отказал в доступе (HTTP %s). "
                "Проверьте ключи (%s) или лимит сервиса.",
                self._service_label,
                status_code,
                self._auth_hint,
            )
            return True
        if status_code == 429:
            logger.error(
                "[GEOCODER] Исчерпан дневной лимит %s (HTTP 429).",
                self._service_label,
            )
            return True
        if status_code >= 400:
            logger.error(
                "[GEOCODER] %s вернул HTTP %s для запроса %r",
                self._service_label,
                status_code,
                text,
            )
            return True
        return False

    def _post_and_parse(
        self,
        body: Any,
        text: str,
        *,
        max_qc_geo: int = MAX_ACCEPTABLE_QC_GEO,
    ) -> tuple[float, float] | None:
        """
        Отправляет тело запроса в DaData и разбирает координаты.

        Аргументы:
            body: JSON-тело POST.
            text: исходный запрос — для логов.
            max_qc_geo: порог ``qc_geo`` для приёмки точки.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        self.last_qc_geo = None
        try:
            response = httpx.post(
                self._request_url(),
                json=body,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            logger.exception("[GEOCODER] Сетевая ошибка %s: %r", self._service_label, text)
            return None

        if self._handle_http_status(response.status_code, text):
            return None

        try:
            payload: Any = response.json()
        except ValueError:
            logger.exception(
                "[GEOCODER] Некорректный JSON от %s: %r",
                self._service_label,
                text,
            )
            return None

        item = self._extract_item(payload, text)
        if item is None:
            return None

        parsed = coords_from_dadata_item(item, text, max_qc_geo=max_qc_geo)
        if parsed is None:
            return None
        point, qc_geo = parsed
        self.last_qc_geo = qc_geo
        return point

    def _geocode_once(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Выполняет один HTTP-запрос к DaData и разбирает координаты.

        Аргументы:
            text: строка адреса.
            city: город для ограничения поиска; подклассы решают сами.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return self._post_and_parse(self._request_body(text, city=city), text)

    def geocode_city_center_sync(self, city_name: str) -> tuple[float, float] | None:
        """
        Геокодирует центр города для ``meta.lat``/``meta.lon``.

        Для центра города допускается грубый ``qc_geo`` (населённый пункт).
        Неоднозначные названия уточняются через ``CITY_CENTER_HINTS``.

        Аргументы:
            city_name: название города из меты файла.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        query = CITY_CENTER_HINTS.get(city_name, city_name)
        return self._geocode_city_center(query)

    def _geocode_city_center(self, query: str) -> tuple[float, float] | None:
        """Запрос центра: сначала с ограничением уровня города, затем без."""
        raise NotImplementedError

    def geocode_sync(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Синхронно переводит адрес в координаты.

        Аргументы:
            text: строка адреса.
            city: город для ограничения поиска; подклассы решают сами.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return self._geocode_once(text, city)

    async def geocode(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Переводит адрес в координаты, не блокируя цикл событий.

        Аргументы:
            text: строка адреса.
            city: город для ограничения поиска; подклассы решают сами.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        return await asyncio.to_thread(self.geocode_sync, text, city)


class DadataSuggestionsGeocoder(_DadataBase):
    """Клиент API подсказок адресов DaData (основной провайдер)."""

    _service_label = "DaData Подсказки"
    _auth_hint = "DADATA_API_KEY"

    def __init__(self) -> None:
        """Создаёт клиент; нужен только ``DADATA_API_KEY``."""
        api_key = settings.dadata_api_key.strip()
        if not api_key:
            raise RuntimeError("Не задан ключ DaData. Укажите переменную окружения DADATA_API_KEY.")
        super().__init__(api_key)

    def _request_url(self) -> str:
        """URL API подсказок."""
        return SUGGEST_ADDRESS_URL

    def _request_body(self, text: str, city: str | None = None) -> Any:
        """Тело: query и count=1; при городе — locations и restrict_value."""
        payload: dict[str, Any] = {"query": text, "count": 1}
        if city is not None:
            payload["locations"] = [{"city": city}]
            payload["restrict_value"] = True
        return payload

    def _geocode_city_center(self, query: str) -> tuple[float, float] | None:
        """Центр города: сначала bound city→settlement, затем без ограничения."""
        bound_body: dict[str, Any] = {
            "query": query,
            "count": 1,
            "from_bound": {"value": "city"},
            "to_bound": {"value": "settlement"},
        }
        point = self._post_and_parse(bound_body, query, max_qc_geo=MAX_CITY_CENTER_QC_GEO)
        if point is not None:
            return point
        return self._post_and_parse(
            {"query": query, "count": 1},
            query,
            max_qc_geo=MAX_CITY_CENTER_QC_GEO,
        )

    def _extract_item(self, payload: Any, text: str) -> dict[str, Any] | None:
        """Достаёт ``data`` первой подсказки."""
        if not isinstance(payload, dict):
            logger.info(
                "[GEOCODER] DaData Подсказки: неожиданный формат ответа на %r",
                text,
            )
            return None
        suggestions = payload.get("suggestions")
        if not isinstance(suggestions, list) or not suggestions:
            logger.info("[GEOCODER] DaData Подсказки: пустой ответ на %r", text)
            return None
        first = suggestions[0]
        if not isinstance(first, dict):
            logger.info("[GEOCODER] DaData Подсказки: неожиданный элемент на %r", text)
            return None
        data = first.get("data")
        if not isinstance(data, dict):
            logger.info("[GEOCODER] DaData Подсказки: нет data в ответе на %r", text)
            return None
        return data

    def geocode_sync(self, text: str, city: str | None = None) -> tuple[float, float] | None:
        """
        Синхронно переводит адрес в координаты.

        При неудаче с ограничением по городу (пустой ответ или грубый
        ``qc_geo``) один раз повторяет запрос без ``locations`` и
        ``restrict_value``. Город остаётся в тексте: если он стоял префиксом
        («Адлер, ул. …»), на повторе переносится в конец — иначе DaData
        не находит адреса в районах, которые в ФИАС не являются городом.

        Аргументы:
            text: строка адреса.
            city: город для ограничения поиска или None.

        Возвращает:
            Пару (широта, долгота) либо None.
        """
        point = self._geocode_once(text, city)
        if point is not None or city is None:
            return point
        prefix = f"{city}, "
        retry_text = f"{text[len(prefix) :]}, {city}" if text.startswith(prefix) else text
        logger.info(
            "[GEOCODER] DaData Подсказки: повтор без ограничения по городу для %r",
            retry_text,
        )
        return self._geocode_once(retry_text, city=None)


class DadataCleanerGeocoder(_DadataBase):
    """Клиент API стандартизации адресов DaData (Cleaner).

    Бесплатно только 100 запросов, дальше 0,2 ₽ за запись — поэтому провайдер
    не основной; включается точечно через ``GEOCODER_PROVIDER=dadata_cleaner``.
    """

    _service_label = "DaData Cleaner"
    _auth_hint = "DADATA_API_KEY и DADATA_SECRET_KEY"

    def __init__(self) -> None:
        """Создаёт клиент; оба ключа должны быть заданы в окружении."""
        api_key = settings.dadata_api_key.strip()
        secret_key = settings.dadata_secret_key.strip()
        if not api_key or not secret_key:
            raise RuntimeError(
                "Не заданы ключи DaData Cleaner. Укажите переменные окружения "
                "DADATA_API_KEY и DADATA_SECRET_KEY."
            )
        super().__init__(api_key)
        self._secret_key = secret_key

    def _headers(self) -> dict[str, str]:
        """Заголовки Cleaner: Token и X-Secret."""
        headers = self._auth_headers()
        headers["X-Secret"] = self._secret_key
        return headers

    def _request_url(self) -> str:
        """URL Cleaner API."""
        return CLEAN_ADDRESS_URL

    def _request_body(self, text: str, city: str | None = None) -> Any:
        """Тело — JSON-массив из одной строки адреса."""
        return [text]

    def _geocode_city_center(self, query: str) -> tuple[float, float] | None:
        """Центр города через Cleaner: одна строка запроса."""
        return self._post_and_parse([query], query, max_qc_geo=MAX_CITY_CENTER_QC_GEO)

    def _extract_item(self, payload: Any, text: str) -> dict[str, Any] | None:
        """Достаёт первый элемент массива ответа Cleaner."""
        if not isinstance(payload, list) or not payload:
            logger.info("[GEOCODER] DaData Cleaner: пустой ответ на %r", text)
            return None
        item = payload[0]
        if not isinstance(item, dict):
            logger.info(
                "[GEOCODER] DaData Cleaner: неожиданный формат ответа на %r",
                text,
            )
            return None
        return item
