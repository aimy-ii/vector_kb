"""Тесты расчёта расстояния и проверки координат."""

from __future__ import annotations

from app.services.directory_service.geo import distance_km, is_valid_point


def test_distance_same_point_is_zero() -> None:
    """Одна и та же точка даёт нулевое расстояние."""
    assert distance_km(55.75, 37.62, 55.75, 37.62) == 0.0


def test_distance_moscow_spb_about_634_km() -> None:
    """Москва — Санкт-Петербург около 634 км с допуском ±10."""
    distance = distance_km(55.7558, 37.6173, 59.9343, 30.3351)
    assert abs(distance - 634.0) <= 10.0


def test_distance_order_independent() -> None:
    """Расстояние не зависит от порядка аргументов."""
    a = distance_km(55.7558, 37.6173, 59.9343, 30.3351)
    b = distance_km(59.9343, 30.3351, 55.7558, 37.6173)
    assert abs(a - b) < 1e-9


def test_is_valid_point_rejects_none_and_out_of_range() -> None:
    """None и выход за диапазон отклоняются, валидная пара проходит."""
    assert is_valid_point(None, 30.0) is False
    assert is_valid_point(55.0, None) is False
    assert is_valid_point(None, None) is False
    assert is_valid_point(91.0, 30.0) is False
    assert is_valid_point(55.0, 181.0) is False
    assert is_valid_point(-91.0, 0.0) is False
    assert is_valid_point(0.0, -181.0) is False
    assert is_valid_point(55.75, 37.62) is True
    assert is_valid_point(-90.0, 180.0) is True
