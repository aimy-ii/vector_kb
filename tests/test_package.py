"""Офлайн-тесты пакета `vektor_directory`: без сети, на встроенных данных."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from vektor_directory import city_enum, get_branch, get_city, resolve_city
from vektor_directory.loader import load
from vektor_directory.lookup import branch_enum


def _walk(value: Any) -> str:
    """Склеивает значение в строку для поиска запрещённых фрагментов."""
    return json.dumps(value, ensure_ascii=False)


def test_public_imports() -> None:
    """Публичные функции импортируются из корня пакета."""
    assert callable(get_city)
    assert callable(get_branch)
    assert callable(city_enum)
    assert callable(resolve_city)


def test_city_enum_unique_and_nonempty() -> None:
    """city_enum() не пуст, слаги уникальны."""
    slugs = city_enum()
    assert slugs
    assert len(slugs) == len(set(slugs))


def test_branch_enum_prefixed_by_city() -> None:
    """branch_enum(город) даёт слаги, начинающиеся со слага города."""
    city = city_enum()[0]
    branches = branch_enum(city)
    assert branches
    for slug in branches:
        assert slug.startswith(city)


def test_city_and_branch_slugs_disjoint() -> None:
    """Слаги городов и филиалов не пересекаются."""
    cities = set(city_enum())
    branches: set[str] = set()
    for city in cities:
        branches.update(branch_enum(city))
    assert cities.isdisjoint(branches)


def test_get_city_shape() -> None:
    """get_city содержит категории, автомобили, телефон."""
    city = get_city(city_enum()[0])
    assert city is not None
    assert "категории" in city
    assert "автомобили" in city
    assert "телефон" in city


def test_get_city_has_no_prices() -> None:
    """get_city не содержит tariffs, promos, слова «цена» и символа ₽."""
    for slug in city_enum():
        meta = get_city(slug)
        assert meta is not None
        assert "tariffs" not in meta
        assert "promos" not in meta
        blob = _walk(meta)
        assert "цена" not in blob.lower()
        assert "₽" not in blob


def test_get_branch_shape() -> None:
    """get_branch даёт адрес, тип, статус."""
    city = city_enum()[0]
    branch = get_branch(branch_enum(city)[0])
    assert branch is not None
    assert branch["адрес"]
    assert branch["тип"] in ("учебный офис", "автодром")
    assert branch["статус"] in ("работает", "скоро открытие")


def test_resolve_city_aliases() -> None:
    """Разговорные и официальные названия Петербурга сходятся в один слаг."""
    expected = resolve_city("Санкт-Петербург")
    assert expected == "sankt-peterburg"
    assert resolve_city("Питер") == expected
    assert resolve_city("спб") == expected


def test_resolve_city_unknown() -> None:
    """Городов вне сети и пустой строки в справочнике нет."""
    assert resolve_city("Москва") is None
    assert resolve_city("мск") is None
    assert resolve_city("") is None


def test_load_is_cached() -> None:
    """load() кэшируется: два вызова возвращают один объект."""
    assert load() is load()


def test_package_files_have_no_service_keys() -> None:
    """Ни в одном файле пакета нет ключей conflicts и _review."""
    data_root = resources.files("vektor_directory").joinpath("data")
    for entry in data_root.iterdir():
        if not entry.name.endswith(".json"):
            continue
        city = json.loads(entry.read_text(encoding="utf-8"))
        assert "conflicts" not in city
        assert "_review" not in city
