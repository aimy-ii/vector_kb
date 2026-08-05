"""Подготовка адреса филиала к геокодированию.

Геокодеры разбирают адрес до дома и не понимают внутренние уточнения —
этаж, офис, помещение. Строения и корпуса в российском OSM заполнены
неровно: дом без строения находится чаще, чем с ним. Сокращения вроде
«пр-кт им.» тоже сбивают разбор.

Результат используется только как строка запроса. В справочнике адрес
остаётся полным: его произносит бот, и по нему клиент приходит в офис.
"""

from __future__ import annotations

import re

_ABBR = (
    (re.compile(r"\bпр-кт\b|\bпросп\b\.?|\bпр\.(?=\s)", re.IGNORECASE), "проспект"),
    (re.compile(r"\bпр-д\b", re.IGNORECASE), "проезд"),
    (re.compile(r"\bб-р\b|\bбул\b\.?", re.IGNORECASE), "бульвар"),
    (re.compile(r"\bпер\b\.?", re.IGNORECASE), "переулок"),
    (re.compile(r"\bнаб\b\.?", re.IGNORECASE), "набережная"),
    (re.compile(r"\bш\.(?=\s)", re.IGNORECASE), "шоссе"),
    (re.compile(r"\bпл\b\.?(?=\s)", re.IGNORECASE), "площадь"),
    (re.compile(r"\bмкр\b\.?|\bмк-н\b", re.IGNORECASE), "микрорайон"),
    (re.compile(r"\bим\b\.?\s*", re.IGNORECASE), ""),
)

_CUT_FROM = re.compile(
    r"[,\s]*(?:\d+\s*)?(?:этаж|эт\.|офис|оф\.|каб\.|кабинет|пом\.|помещение"
    r"|стр\.|строение|корп\.|корпус|литер[аоы]?)(?!\w).*$",
    re.IGNORECASE,
)

_COMMA_AFTER_ABBR = re.compile(r"\b(ул|пр|пер|б-р|наб|ш|пл|д|стр|корп)\s*,\s*(?=\S)")
_SPACES = re.compile(r"\s{2,}")


def normalize_for_geocoder(address: str) -> str:
    """
    Готовит адрес филиала к отправке в геокодер.

    Раскрывает сокращения, обрезает всё начиная с первого внутреннего
    уточнения — этажа, офиса, строения, корпуса, — чинит запятую вместо
    точки в сокращениях и схлопывает пробелы.

    Аргументы:
        address: адрес филиала как он лежит в справочнике.

    Возвращает:
        Очищенную строку. Если после чистки ничего не осталось, возвращает
        исходный адрес без изменений.
    """
    cleaned = address.replace("\xa0", " ")
    cleaned = _COMMA_AFTER_ABBR.sub(r"\1. ", cleaned)
    for pattern, replacement in _ABBR:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = _CUT_FROM.sub("", cleaned)
    cleaned = _SPACES.sub(" ", cleaned)
    cleaned = cleaned.strip(" ,.;")
    return cleaned or address
