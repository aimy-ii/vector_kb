"""Проверки целостности координат филиалов относительно центра города.

Нужны, чтобы ловить перепутанные города (филиал Железногорска с точкой
в Красноярске) до того, как бот отправит клиента за десятки километров.
"""

from __future__ import annotations

from typing import Any

from app.services.directory_service.address import extract_own_city
from app.services.directory_service.geo import distance_km, is_valid_point

#: Максимальное расстояние филиала от центра города файла (км).
#: Запас на пригороды в том же файле; перепутанный соседний город ловится.
MAX_BRANCH_FROM_CITY_KM = 50.0


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
