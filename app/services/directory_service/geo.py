"""Работа с координатами при подборе филиала.

Расстояние считает `geopy.distance.great_circle` — формула гаверсинуса из
библиотеки. Более точный `geodesic` здесь избыточен: он расходится с
`great_circle` на метр и работает в десять раз медленнее, а филиалы разнесены
по городу на километры.
"""

from __future__ import annotations

from geopy.distance import great_circle


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Считает расстояние по прямой между двумя точками.

    Аргументы:
        lat1: широта первой точки в градусах.
        lon1: долгота первой точки в градусах.
        lat2: широта второй точки в градусах.
        lon2: долгота второй точки в градусах.

    Возвращает:
        Расстояние в километрах.
    """
    return great_circle((lat1, lon1), (lat2, lon2)).km


def is_valid_point(lat: float | None, lon: float | None) -> bool:
    """
    Проверяет, что пара координат заполнена и лежит в допустимом диапазоне.

    Аргументы:
        lat: широта или None.
        lon: долгота или None.

    Возвращает:
        True, если точкой можно пользоваться в расчётах.
    """
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
