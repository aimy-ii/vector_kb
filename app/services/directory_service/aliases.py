"""Разговорные названия городов → слаги справочника."""

from __future__ import annotations

from app.services.directory_service.store import directory_store

CITY_ALIASES: dict[str, str] = {
    "питер": "sankt-peterburg",
    "спб": "sankt-peterburg",
    "петербург": "sankt-peterburg",
    "ебург": "ekaterinburg",
    "екат": "ekaterinburg",
    "нн": "nizhniy-novgorod",
    "нижний": "nizhniy-novgorod",
}


def _normalize(text: str) -> str:
    """Приводит строку к виду для сравнения: нижний регистр, «ё» → «е»."""
    return text.strip().lower().replace("ё", "е")


def _cities() -> dict:
    """Возвращает города из памяти; при пустом кэше подгружает с диска."""
    if not directory_store.cities:
        directory_store.load()
    return directory_store.cities


def resolve_city(text: str) -> str | None:
    """Ищет слаг города по названию или разговорному варианту.

    Сравнивает в нижнем регистре с «ё» приведённой к «е»: сначала точное совпадение
    названия, потом таблица алиасов. Ничего не угадывает — городов вне сети
    (например, Москвы) в справочнике нет, и функция вернёт None.

    Аргументы:
        text: название города или разговорный вариант.

    Возвращает:
        Слаг города или None, если совпадения нет.
    """
    needle = _normalize(text)
    if not needle:
        return None

    for slug, city in _cities().items():
        if _normalize(city["meta"]["city"]) == needle:
            return slug

    return CITY_ALIASES.get(needle)
