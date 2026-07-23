"""Офлайн-тесты справочника: без сети, на реальных файлах из data/."""

from __future__ import annotations

import directory
import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Сбрасывает кэш загрузки перед каждым тестом."""
    directory._load.cache_clear()


def test_cities_have_keys():
    """Каждый город отдаёт слаг, название и число филиалов."""
    cities = directory.list_cities()
    assert cities
    for city in cities:
        assert city["слаг"] and city["город"]
        assert isinstance(city["филиалов"], int)


def test_city_slugs_unique():
    """Слаги городов уникальны — иначе enum сломается."""
    slugs = [c["слаг"] for c in directory.list_cities()]
    assert len(slugs) == len(set(slugs))


def test_branch_slugs_globally_unique():
    """Слаги филиалов уникальны на всю сеть, а не только внутри города."""
    slugs = [b["слаг"] for c in directory.list_cities() for b in directory.list_branches(c["слаг"])]
    assert len(slugs) == len(set(slugs))


def test_branch_slug_starts_with_city():
    """Слаг филиала начинается со слага своего города."""
    for city in directory.list_cities():
        for branch in directory.list_branches(city["слаг"]):
            assert branch["слаг"].startswith(city["слаг"])


def test_get_city_shape():
    """Мета города содержит нужные разделы и не содержит цену."""
    city = directory.get_city(directory.list_cities()[0]["слаг"])
    for key in ("город", "филиалов", "категории", "автомобили", "телефон"):
        assert key in city
    assert "цена" not in city
    assert "price" not in city


def test_get_branch_by_slug():
    """Филиал достаётся по своему слагу и знает свой город."""
    city = directory.list_cities()[0]
    branch_slug = directory.list_branches(city["слаг"])[0]["слаг"]
    branch = directory.get_branch(branch_slug)
    assert branch["город"] == city["город"]
    assert branch["адрес"]
    assert branch["тип"] in ("учебный офис", "автодром")
    assert branch["статус"] in ("работает", "скоро открытие")


def test_unknown_keys_return_none():
    """Несуществующие ключи не роняют справочник."""
    assert directory.get_city("нет-такого") is None
    assert directory.get_branch("нет_такого") is None
    assert directory.list_branches("нет-такого") == []


def test_soon_opening_has_no_hours():
    """У филиала со статусом «скоро открытие» часы работы пустые."""
    for city in directory.list_cities():
        for item in directory.list_branches(city["слаг"]):
            branch = directory.get_branch(item["слаг"])
            if branch["статус"] == "скоро открытие":
                assert branch["часы работы"] is None
                return


def test_faq_answers_not_empty():
    """В мету попадают только вопросы с непустым ответом."""
    for city in directory.list_cities():
        for pair in directory.get_city(city["слаг"])["частые вопросы"]:
            assert pair["ответ"]
