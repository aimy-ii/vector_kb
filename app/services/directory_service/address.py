"""Подготовка адреса филиала к геокодированию.

Геокодеры разбирают адрес до дома и не понимают внутренние уточнения —
этаж, офис, помещение. Строения и корпуса в российском OSM заполнены
неровно: дом без строения находится чаще, чем с ним. DaData (ФИАС)
понимает строения и корпуса, поэтому для неё их можно оставить
(``strip_building=False``). Сокращения вроде «пр-кт им.» тоже сбивают разбор.

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

#: Уточнения внутри здания — срезаются всегда.
_CUT_INTERIOR = re.compile(
    r"[,\s]*(?:\d+\s*)?(?:этаж|эт\.|офис|оф\.|каб\.|кабинет|пом\.|помещение)"
    r"(?!\w).*$",
    re.IGNORECASE,
)

#: Строение/корпус плюс внутренние уточнения — для Nominatim.
_CUT_BUILDING_OR_INTERIOR = re.compile(
    r"[,\s]*(?:\d+\s*)?(?:этаж|эт\.|офис|оф\.|каб\.|кабинет|пом\.|помещение"
    r"|стр\.|строение|корп\.|корпус|литер[аоы]?)(?!\w).*$",
    re.IGNORECASE,
)

_COMMA_AFTER_ABBR = re.compile(r"\b(ул|пр|пер|б-р|наб|ш|пл|д|стр|корп)\s*,\s*(?=\S)")
_SPACES = re.compile(r"\s{2,}")

#: Явное указание населённого пункта в начале адреса: «г. X», «г X», «город X».
#: Имя — одно–три слова с заглавной; «улица Городская» не подходит.
_OWN_CITY_PREFIX = re.compile(
    r"(?iu)^\s*(?:г\.?\s*|город\s+)"
    r"[А-ЯЁA-Z][а-яёa-z]+"
    r"(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2}"
    r"(?=[\s,]|$)"
)


def has_own_city(address: str, city: str) -> bool:
    """
    Проверяет, что в адресе уже указан населённый пункт.

    Ищет название города файла в начале строки либо явную метку «г.» / «город»
    с именем поселения (в том числе составным и отличным от города файла —
    пригороды вроде Мурино в файле Петербурга). Не срабатывает на улицах
    вроде «улица Городская».

    Аргументы:
        address: адрес филиала (обычно уже нормализованный).
        city: название города из меты файла.

    Возвращает:
        True, если город в адресе уже есть и дописывать город файла не нужно.
    """
    if not address:
        return False
    text = address.strip()
    if city:
        name = city.casefold()
        if text.casefold().startswith(name):
            return True
    return _OWN_CITY_PREFIX.search(text) is not None


def normalize_for_geocoder(address: str, *, strip_building: bool = True) -> str:
    """
    Готовит адрес филиала к отправке в геокодер.

    Раскрывает сокращения, обрезает внутренние уточнения (этаж, офис,
    помещение), при ``strip_building=True`` также срезает строение и корпус,
    чинит запятую вместо точки в сокращениях и схлопывает пробелы.

    Аргументы:
        address: адрес филиала как он лежит в справочнике.
        strip_building: если True — срезать строение и корпус (Nominatim);
            если False — оставить их (DaData).

    Возвращает:
        Очищенную строку. Если после чистки ничего не осталось, возвращает
        исходный адрес без изменений.
    """
    cleaned = address.replace("\xa0", " ")
    cleaned = _COMMA_AFTER_ABBR.sub(r"\1. ", cleaned)
    for pattern, replacement in _ABBR:
        cleaned = pattern.sub(replacement, cleaned)
    cut = _CUT_BUILDING_OR_INTERIOR if strip_building else _CUT_INTERIOR
    cleaned = cut.sub("", cleaned)
    cleaned = _SPACES.sub(" ", cleaned)
    cleaned = cleaned.strip(" ,.;")
    return cleaned or address
