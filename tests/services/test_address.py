"""Тесты нормализации адреса перед геокодированием."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.services.directory_service.address import normalize_for_geocoder

#: Набор примеров для проверки формы результата.
_EXAMPLES = (
    "ул. Алексеева, 46, 2 этаж пом. 477",
    "ул. Полтавская, д. 38, стр. 4",
    "Ленинский просп., 128, корп. 2, эт. 2",
    "пр-кт им. Газеты Красноярский Рабочий, 42",
    "ул. Правды, 17, 5 этаж, офис 501",
    "ул. Гайдара 2/1, 2 этаж",
    "ул, Славы, д. 12",
    "ул. Шумяцкого, 2Е",
)


def test_cuts_entire_tail_after_first_refinement() -> None:
    """Хвост от первого уточнения срезается целиком, без остатка номера."""
    assert normalize_for_geocoder("ул. Алексеева, 46, 2 этаж пом. 477") == ("ул. Алексеева, 46")


def test_strips_structure() -> None:
    """Строение срезается — дом без него находится чаще."""
    assert normalize_for_geocoder("ул. Полтавская, д. 38, стр. 4") == ("ул. Полтавская, д. 38")


def test_keeps_structure_when_strip_building_false() -> None:
    """При strip_building=False строение и корпус сохраняются."""
    assert (
        normalize_for_geocoder("ул. Полтавская, д. 38, стр. 4", strip_building=False)
        == "ул. Полтавская, д. 38, стр. 4"
    )
    assert (
        normalize_for_geocoder("Ленинский просп., 128, корп. 2, эт. 2", strip_building=False)
        == "Ленинский проспект, 128, корп. 2"
    )


def test_strips_floor_office_even_without_strip_building() -> None:
    """Этаж и офис срезаются и при strip_building=False."""
    assert (
        normalize_for_geocoder("ул. Правды, 17, 5 этаж, офис 501", strip_building=False)
        == "ул. Правды, 17"
    )


def test_expands_prospekt_and_strips_corpus() -> None:
    """«просп.» раскрывается, корпус и этаж срезаются."""
    assert normalize_for_geocoder("Ленинский просп., 128, корп. 2, эт. 2") == (
        "Ленинский проспект, 128"
    )


def test_expands_pr_kt_im() -> None:
    """«пр-кт им.» раскрывается в «проспект» без «им.»."""
    assert normalize_for_geocoder("пр-кт им. Газеты Красноярский Рабочий, 42") == (
        "проспект Газеты Красноярский Рабочий, 42"
    )


def test_strips_floor_and_office() -> None:
    """Этаж и офис срезаются."""
    assert normalize_for_geocoder("ул. Правды, 17, 5 этаж, офис 501") == ("ул. Правды, 17")


def test_keeps_fraction_house_number() -> None:
    """Дробь в номере дома сохраняется."""
    assert normalize_for_geocoder("ул. Гайдара 2/1, 2 этаж") == "ул. Гайдара 2/1"


def test_comma_after_abbreviation_becomes_dot() -> None:
    """Запятая после сокращения превращается в точку."""
    assert normalize_for_geocoder("ул, Славы, д. 12") == "ул. Славы, д. 12"


def test_no_dangling_punctuation_or_double_spaces() -> None:
    """В результатах нет висячих запятых, точек и двойных пробелов."""
    for raw in _EXAMPLES:
        cleaned = normalize_for_geocoder(raw)
        assert cleaned == cleaned.strip(" ,.;")
        assert "  " not in cleaned
        assert not cleaned.endswith(",")
        assert not cleaned.endswith(".")


def test_clean_address_unchanged() -> None:
    """Адрес без уточнений не меняется."""
    assert normalize_for_geocoder("ул. Шумяцкого, 2Е") == "ул. Шумяцкого, 2Е"


def test_only_refinement_returns_original() -> None:
    """Адрес из одного уточнения возвращается как есть, а не пустым."""
    assert normalize_for_geocoder("5 этаж") == "5 этаж"
    assert normalize_for_geocoder("офис 501") == "офис 501"


def test_all_directory_addresses_normalize_cleanly() -> None:
    """После нормализации ни один из 235 адресов не пустой и не корявый."""
    data_dir: Path = settings.directory_data_dir
    count = 0
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            count += 1
            address = branch.get("address") or ""
            cleaned = normalize_for_geocoder(address)
            assert cleaned, f"{path.name}: {branch.get('id')} стал пустым"
            assert not cleaned.endswith(","), f"{path.name}: {cleaned!r}"
            assert not cleaned.endswith("."), f"{path.name}: {cleaned!r}"
            assert "  " not in cleaned, f"{path.name}: {cleaned!r}"
    assert count == 235
