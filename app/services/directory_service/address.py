"""Подготовка адреса филиала к геокодированию.

Геокодеры разбирают адрес до дома и не понимают внутренние уточнения —
этаж, офис, помещение, торговый центр, бытовые пометки. Строения и корпуса
в российском OSM заполнены неровно: дом без строения находится чаще, чем
с ним. DaData (ФИАС) понимает строения и корпуса, поэтому для неё их можно
оставить (``strip_building=False``). Сокращения вроде «пр-кт им.» тоже
сбивают разбор.

Результат используется только как строка запроса. В справочнике адрес
остаётся полным: его произносит бот, и по нему клиент приходит в офис.
"""

from __future__ import annotations

import re

#: Раскрываемые сокращения: слово без хвостового пробела.
#: Пробел после слова — только если дальше сразу буква/цифра («Пер.Школьный»).
_ABBR = (
    (re.compile(r"\bпр-кт\b\.?|\bпросп\b\.?", re.IGNORECASE), "проспект"),
    (re.compile(r"\bпр\b\.", re.IGNORECASE), "проспект"),
    (re.compile(r"\bпр-д\b\.?", re.IGNORECASE), "проезд"),
    (re.compile(r"\bб-р\b\.?|\bбул\b\.?", re.IGNORECASE), "бульвар"),
    (re.compile(r"\bпер\b\.?", re.IGNORECASE), "переулок"),
    (re.compile(r"\bнаб\b\.?", re.IGNORECASE), "набережная"),
    (re.compile(r"\bш\.", re.IGNORECASE), "шоссе"),
    (re.compile(r"\bпл\b\.?", re.IGNORECASE), "площадь"),
    (re.compile(r"\bмкр\b\.?|\bмк-н\b", re.IGNORECASE), "микрорайон"),
    (re.compile(r"\bим\b\.?\s*", re.IGNORECASE), ""),
)

#: Точка после сокращения без пробела: «ул.Ленина», «д.5».
_ABBR_DOT_SPACE = re.compile(r"\b(ул|д|стр|корп)\.(?=\S)", re.IGNORECASE)


def _expand_abbr(text: str, pattern: re.Pattern[str], word: str) -> str:
    """Подставляет слово; пробел — только если дальше сразу буква или цифра."""

    def repl(match: re.Match[str]) -> str:
        nxt = text[match.end() : match.end() + 1]
        if word and nxt and nxt.isalnum():
            return f"{word} "
        return word

    return pattern.sub(repl, text)


#: Круглые скобки с любым содержимым — срезаются раньше остальных хвостов.
_PARENS = re.compile(r"\([^()]*\)")

#: Метка торгового/бизнес-центра в начале: «ТЦ Титул, улица …».
_TC_LABEL = r"(?:ТЦ|ТРЦ|ТК|МФК|БЦ|ТРК)"
_TC_AT_START = re.compile(rf"(?iu)^\s*{_TC_LABEL}\b[^,]*,\s*")

#: Уточнения внутри здания и прочие хвосты — срезаются всегда.
_CUT_INTERIOR = re.compile(
    r"(?:"
    r"[,\s]*(?:\d+\s*)?(?:этаж|эт\.|офис|оф\.|каб\.|кабинет|пом\.|помещение)(?!\w)"
    rf"|[,\s]*{_TC_LABEL}\b"
    r"|[,\s]*(?:домофон|отдельный\s+вход|вход|парковка)\b"
    r"|[,\s]*\d+-?(?:ая|я)\s*очередь\b"
    r").*$",
    re.IGNORECASE,
)

#: Строение/корпус плюс внутренние уточнения — для Nominatim.
_CUT_BUILDING_OR_INTERIOR = re.compile(
    r"(?:"
    r"[,\s]*(?:\d+\s*)?(?:этаж|эт\.|офис|оф\.|каб\.|кабинет|пом\.|помещение"
    r"|стр\.|строение|корп\.|корпус|литер[аоы]?)(?!\w)"
    rf"|[,\s]*{_TC_LABEL}\b"
    r"|[,\s]*(?:домофон|отдельный\s+вход|вход|парковка)\b"
    r"|[,\s]*\d+-?(?:ая|я)\s*очередь\b"
    r").*$",
    re.IGNORECASE,
)

_COMMA_AFTER_ABBR = re.compile(r"\b(ул|пр|пер|б-р|наб|ш|пл|д|стр|корп)\s*,\s*(?=\S)")
_SPACES = re.compile(r"\s{2,}")

#: Явная метка населённого пункта в начале адреса.
#: «д.» перед цифрой — номер дома, не деревня. «Нижняя Омка» без метки не ловится.
_OWN_CITY = re.compile(
    r"(?iu)^\s*(?:"
    r"город\s+"
    r"|г\.\s*"
    r"|г\s+"
    r"|рабочий\s+посёлок\s+"
    r"|рабочий\s+поселок\s+"
    r"|р\.?\s*п\.?\s*"
    r"|рп\s+"
    r"|пгт\.?\s*"
    r"|посёлок\s+городского\s+типа\s+"
    r"|поселок\s+городского\s+типа\s+"
    r"|посёлок\s+"
    r"|поселок\s+"
    r"|пос\.\s*"
    r"|пос\s+"
    r"|село\s+"
    r"|с\.\s*"
    r"|деревня\s+"
    r"|д\.(?!\s*\d)\s*"
    r")"
    r"([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2})"
    r"(?=[\s,]|$)"
)


def extract_own_city(address: str) -> str | None:
    """
    Извлекает название населённого пункта из начала адреса.

    Распознаёт метки «г.», «город», «р.п.», «рп», «пгт», «посёлок»/«поселок»/
    «пос.», «село»/«с.», «деревня»/«д.» (но не «д. 12» — это дом). Без метки
    («Нижняя Омка») не угадывает.

    Аргументы:
        address: адрес филиала (обычно уже нормализованный).

    Возвращает:
        Название поселения или None, если метки нет.
    """
    if not address:
        return None
    match = _OWN_CITY.search(address.strip())
    return match.group(1) if match else None


def has_own_city(address: str, city: str) -> bool:
    """
    Проверяет, что в адресе уже указан населённый пункт.

    Ищет название города файла в начале строки либо явную метку населённого
    пункта с именем поселения (в том числе составным и отличным от города
    файла — пригороды вроде Мурино в файле Петербурга). Не срабатывает на
    улицах вроде «улица Городская».

    Аргументы:
        address: адрес филиала (обычно уже нормализованный).
        city: название города из меты файла.

    Возвращает:
        True, если город в адресе уже есть и дописывать город файла не нужно.
    """
    if not address:
        return False
    if extract_own_city(address) is not None:
        return True
    if city:
        return address.strip().casefold().startswith(city.casefold())
    return False


def normalize_for_geocoder(address: str, *, strip_building: bool = True) -> str:
    """
    Готовит адрес филиала к отправке в геокодер.

    Раскрывает сокращения, срезает скобочные уточнения, торговые центры,
    бытовые пометки и внутренние уточнения (этаж, офис, помещение), при
    ``strip_building=True`` также срезает строение и корпус, чинит запятую
    вместо точки в сокращениях и схлопывает пробелы.

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
    cleaned = _ABBR_DOT_SPACE.sub(r"\1. ", cleaned)
    for pattern, replacement in _ABBR:
        cleaned = _expand_abbr(cleaned, pattern, replacement)
    while True:
        updated = _PARENS.sub("", cleaned)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = _TC_AT_START.sub("", cleaned)
    cut = _CUT_BUILDING_OR_INTERIOR if strip_building else _CUT_INTERIOR
    cleaned = cut.sub("", cleaned)
    cleaned = _SPACES.sub(" ", cleaned)
    cleaned = cleaned.strip(" ,.;")
    return cleaned or address
