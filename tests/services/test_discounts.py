"""Офлайн-тесты раздела скидок в карточке города.

Работают на реальных встроенных данных справочника, без сети.
"""

from __future__ import annotations

import copy
from typing import Any

from app.services.directory_service.api import city_detail
from app.services.directory_service.store import directory_store

#: Фраза, которая должна быть у каждого города после заполнения.
_STUDENT_PHRASE = "студентам и школьникам скидка до 1000 рублей"


def test_all_city_files_have_nonempty_discounts() -> None:
    """Раздел discounts есть во всех файлах городов и непуст в каждом."""
    if not directory_store.cities:
        directory_store.load()
    assert directory_store.cities
    for slug, city in directory_store.cities.items():
        discounts = city.get("discounts")
        assert isinstance(discounts, list), slug
        assert discounts, slug


def test_city_detail_discounts_nonempty_strings() -> None:
    """city_detail(slug).discounts непуст и содержит только непустые строки."""
    if not directory_store.cities:
        directory_store.load()
    for slug in directory_store.cities:
        detail = city_detail(slug)
        assert detail is not None
        assert detail.discounts
        for item in detail.discounts:
            assert isinstance(item, str)
            assert item.strip()


def test_city_detail_has_student_discount_phrase() -> None:
    """У любого города в списке скидок есть фраза про студентов и школьников."""
    if not directory_store.cities:
        directory_store.load()
    slug = next(iter(directory_store.cities))
    detail = city_detail(slug)
    assert detail is not None
    assert _STUDENT_PHRASE in detail.discounts


def test_city_detail_missing_discounts_returns_empty() -> None:
    """Город без раздела discounts не роняет карточку: отдаётся пустой список."""
    if not directory_store.cities:
        directory_store.load()
    slug = next(iter(directory_store.cities))
    original = directory_store.cities[slug]
    stub = copy.deepcopy(original)
    stub.pop("discounts", None)
    directory_store._cities = {**directory_store.cities, slug: stub}
    try:
        detail = city_detail(slug)
        assert detail is not None
        assert detail.discounts == []
    finally:
        directory_store.load()


def test_city_detail_filters_non_string_discounts() -> None:
    """Нерелевантные типы внутри списка отфильтровываются."""
    if not directory_store.cities:
        directory_store.load()
    slug = next(iter(directory_store.cities))
    original = directory_store.cities[slug]
    stub: dict[str, Any] = copy.deepcopy(original)
    stub["discounts"] = ["текст", None, 123, "  "]
    directory_store._cities = {**directory_store.cities, slug: stub}
    try:
        detail = city_detail(slug)
        assert detail is not None
        assert detail.discounts == ["текст"]
    finally:
        directory_store.load()
