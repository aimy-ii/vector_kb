"""Проверки целостности координат филиалов относительно центра города.

Нужны, чтобы ловить перепутанные города (филиал Железногорска с точкой
в Красноярске) до того, как бот отправит клиента за десятки километров.
Также ловят дубли адресов между городами и скопированные координаты.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

from app.services.directory_service.address import extract_own_city, normalize_for_geocoder
from app.services.directory_service.geo import distance_km, is_valid_point

#: Максимальное расстояние филиала от центра города файла (км).
#: Запас на пригороды в том же файле; перепутанный соседний город ловится.
MAX_BRANCH_FROM_CITY_KM = 50.0

#: Сокращения улицы/дома, которые мешают сравнивать адреса между файлами.
_COMPARE_NOISE = re.compile(r"\b(ул\.?|улица|д\.?|дом)\b", re.IGNORECASE)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize_address_key(address: str) -> str:
    """
    Строит ключ сравнения адреса без регистра, пробелов и сокращений.

    Сначала срезает этаж/офис через ``normalize_for_geocoder``, затем убирает
    «ул.»/«д.» и прочий шум, чтобы «ул. Кирова, 23» и «Кирова 23» совпали.

    Аргументы:
        address: адрес филиала как в справочнике.

    Возвращает:
        Нормализованный ключ для сравнения; пустая строка для пустого адреса.
    """
    if not address:
        return ""
    cleaned = normalize_for_geocoder(address)
    text = unicodedata.normalize("NFKC", cleaned).casefold().replace("ё", "е")
    text = _COMPARE_NOISE.sub(" ", text)
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def duplicate_addresses_across_cities(
    cities: list[dict[str, Any]],
) -> list[tuple[str, list[str]]]:
    """
    Находит один и тот же адрес в файлах разных городов.

    Сравнение идёт по ``normalize_address_key``. Совпадения внутри одного
    города не считаются нарушением — ловится только кросс-городской дубль.

    Аргументы:
        cities: список JSON городов со ``meta.city`` и филиалами.

    Возвращает:
        Список пар (ключ адреса, метки «город:id»), отсортированный по ключу.
    """
    by_key: dict[str, list[str]] = defaultdict(list)
    for city in cities:
        city_name = str((city.get("meta") or {}).get("city") or "")
        for branch in city.get("branches", {}).get("items", []):
            key = normalize_address_key(branch.get("address") or "")
            if not key:
                continue
            by_key[key].append(f"{city_name}:{branch.get('id') or ''}")

    duplicates: list[tuple[str, list[str]]] = []
    for key, labels in by_key.items():
        cities_in_group = {label.split(":", 1)[0] for label in labels}
        if len(cities_in_group) > 1:
            duplicates.append((key, sorted(labels)))
    duplicates.sort(key=lambda item: item[0])
    return duplicates


def duplicate_coordinates(
    cities: list[dict[str, Any]],
) -> list[tuple[tuple[float, float], list[str]]]:
    """
    Находит филиалы с точно совпадающими широтой и долготой.

    Одинаковая точка у разных записей значит, что координата скопирована,
    а не определена независимо — клиент услышит один адрес дважды.

    Аргументы:
        cities: список JSON городов со ``meta.city`` и филиалами.

    Возвращает:
        Список пар ((lat, lon), метки «город:id»), отсортированный по точке.
    """
    by_point: dict[tuple[float, float], list[str]] = defaultdict(list)
    for city in cities:
        city_name = str((city.get("meta") or {}).get("city") or "")
        for branch in city.get("branches", {}).get("items", []):
            lat, lon = branch.get("lat"), branch.get("lon")
            if not is_valid_point(lat, lon):
                continue
            point = (float(lat), float(lon))
            by_point[point].append(f"{city_name}:{branch.get('id') or ''}")

    duplicates: list[tuple[tuple[float, float], list[str]]] = []
    for point, labels in by_point.items():
        if len(labels) > 1:
            duplicates.append((point, sorted(labels)))
    duplicates.sort(key=lambda item: item[0])
    return duplicates


def branches_far_from_city_center(
    city: dict[str, Any],
    *,
    max_km: float = MAX_BRANCH_FROM_CITY_KM,
) -> list[tuple[str, float]]:
    """
    Находит филиалы, чьи координаты слишком далеко от центра города файла.

    Филиалы с явным населённым пунктом в адресе (``extract_own_city``)
    пропускаются: они законно лежат в другом поселении того же файла.

    Аргументы:
        city: JSON города со ``meta.lat``/``meta.lon`` и списком филиалов.
        max_km: порог расстояния в километрах.

    Возвращает:
        Список пар (id филиала, расстояние в км), отсортированный по id.
        Пустой список, если центр города не задан.
    """
    meta = city.get("meta") or {}
    city_lat = meta.get("lat")
    city_lon = meta.get("lon")
    if not is_valid_point(city_lat, city_lon):
        return []

    far: list[tuple[str, float]] = []
    for branch in city.get("branches", {}).get("items", []):
        address = branch.get("address") or ""
        if extract_own_city(address) is not None:
            continue
        b_lat, b_lon = branch.get("lat"), branch.get("lon")
        if not is_valid_point(b_lat, b_lon):
            continue
        distance = distance_km(float(b_lat), float(b_lon), float(city_lat), float(city_lon))
        if distance > max_km:
            far.append((str(branch.get("id") or ""), distance))
    far.sort(key=lambda item: item[0])
    return far
