"""Офлайн-тесты справочника: без сети, на реальных файлах."""

from __future__ import annotations

import pytest
from app.services.directory_service import (
    get_branch,
    get_city,
    list_branches,
    list_cities,
)
from app.services.directory_service.store import directory_store


@pytest.fixture(autouse=True)
def _reload_store() -> None:
    """Перечитывает справочник перед каждым тестом."""
    directory_store.load()


def test_cities_have_keys() -> None:
    """Каждый город отдаёт слаг, название и число филиалов."""
    cities = list_cities()
    assert cities
    for city in cities:
        assert city["слаг"] and city["город"]
        assert isinstance(city["филиалов"], int)


def test_city_slugs_unique() -> None:
    """Слаги городов уникальны — иначе enum сломается."""
    slugs = [c["слаг"] for c in list_cities()]
    assert len(slugs) == len(set(slugs))


def test_branch_slugs_globally_unique() -> None:
    """Слаги филиалов уникальны на всю сеть, а не только внутри города."""
    slugs = [b["слаг"] for c in list_cities() for b in list_branches(c["слаг"])]
    assert len(slugs) == len(set(slugs))


def test_branch_slug_starts_with_city() -> None:
    """Слаг филиала начинается со слага своего города."""
    for city in list_cities():
        for branch in list_branches(city["слаг"]):
            assert branch["слаг"].startswith(city["слаг"])


def test_get_city_shape() -> None:
    """Мета города содержит нужные разделы и не содержит цену."""
    city = get_city(list_cities()[0]["слаг"])
    for key in ("город", "филиалов", "категории", "автомобили", "телефон"):
        assert key in city
    assert "цена" not in city
    assert "price" not in city


def test_get_branch_by_slug() -> None:
    """Филиал достаётся по своему слагу и знает свой город."""
    city = list_cities()[0]
    branch_slug = list_branches(city["слаг"])[0]["слаг"]
    branch = get_branch(branch_slug)
    assert branch["город"] == city["город"]
    assert branch["адрес"]
    assert branch["тип"] in ("учебный офис", "автодром")
    assert branch["статус"] in ("работает", "скоро открытие")


def test_unknown_keys_return_none() -> None:
    """Несуществующие ключи не роняют справочник."""
    assert get_city("нет-такого") is None
    assert get_branch("нет_такого") is None
    assert list_branches("нет-такого") == []


def test_soon_opening_has_no_hours() -> None:
    """У филиала со статусом «скоро открытие» часы работы пустые."""
    for city in list_cities():
        for item in list_branches(city["слаг"]):
            branch = get_branch(item["слаг"])
            if branch["статус"] == "скоро открытие":
                assert branch["часы работы"] is None
                return


def test_faq_answers_not_empty() -> None:
    """В мету попадают только вопросы с непустым ответом."""
    for city in list_cities():
        for pair in get_city(city["слаг"])["частые вопросы"]:
            assert pair["ответ"]
