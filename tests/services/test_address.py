"""Тесты нормализации адреса перед геокодированием."""

from __future__ import annotations

from app.services.directory_service.address import normalize_for_geocoder


def test_strips_floor_and_office_tail() -> None:
    """Хвост с этажом и офисом срезается."""
    assert normalize_for_geocoder("ул. Правды, 17, 5 этаж, офис 501") == "ул. Правды, 17"


def test_tail_variants() -> None:
    """Варианты написания этажа и офиса срезаются."""
    assert normalize_for_geocoder("ул. Тестовая, 1, эт. 4, оф. 415") == "ул. Тестовая, 1"
    assert normalize_for_geocoder("ул. Тестовая, 1, офис 4, этаж 1") == "ул. Тестовая, 1"
    assert normalize_for_geocoder("ул. Тестовая, 1, 2 этаж") == "ул. Тестовая, 1"
    assert normalize_for_geocoder("ул. Тестовая, 1, оф. 204") == "ул. Тестовая, 1"
    assert normalize_for_geocoder("ул. Тестовая, 1, пом. 12") == "ул. Тестовая, 1"


def test_keeps_building_and_structure() -> None:
    """Корпус и строение остаются — они часть адреса дома."""
    assert normalize_for_geocoder("ул. Полтавская, д. 38, стр. 4") == (
        "ул. Полтавская, д. 38, стр. 4"
    )
    assert normalize_for_geocoder("ул. Высотная, 4, стр. 2") == "ул. Высотная, 4, стр. 2"
    assert normalize_for_geocoder("ул. Мира, 10, корп. 2") == "ул. Мира, 10, корп. 2"


def test_comma_after_abbreviation_becomes_dot() -> None:
    """Запятая после сокращения превращается в точку."""
    assert normalize_for_geocoder("ул, Славы, д. 12") == "ул. Славы, д. 12"


def test_collapses_nbsp_and_spaces() -> None:
    """Неразрывный пробел и двойные пробелы схлопываются."""
    assert normalize_for_geocoder("ул.\xa0Славы,  д. 12") == "ул. Славы, д. 12"


def test_clean_address_unchanged() -> None:
    """Адрес без уточнений не меняется."""
    assert normalize_for_geocoder("ул. Шумяцкого, 2Е") == "ул. Шумяцкого, 2Е"


def test_only_tail_returns_original() -> None:
    """Адрес из одного уточнения возвращается как есть, а не пустым."""
    assert normalize_for_geocoder("5 этаж") == "5 этаж"
    assert normalize_for_geocoder("офис 501") == "офис 501"
