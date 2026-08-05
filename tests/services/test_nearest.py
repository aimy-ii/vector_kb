"""Тесты подбора ближайших филиалов на ручных фикстурах."""

from __future__ import annotations

from typing import Any

import pytest
from app.services.directory_service import lookup
from app.services.directory_service.lookup import city_name, nearest_branches


def _branch(
    branch_id: str,
    address: str,
    *,
    lat: float | None,
    lon: float | None,
    is_autodrome: bool = False,
    hours: str = "ПН-ПТ 10:00-19:00",
    landmark: str | None = None,
) -> dict[str, Any]:
    """Собирает минимальную запись филиала для фикстуры."""
    return {
        "id": branch_id,
        "address": address,
        "hours": hours,
        "is_autodrome": is_autodrome,
        "landmark": landmark,
        "lat": lat,
        "lon": lon,
    }


def _city(name: str, branches: list[dict[str, Any]]) -> dict[str, Any]:
    """Собирает минимальную запись города для фикстуры."""
    return {"meta": {"city": name}, "branches": {"items": branches}}


@pytest.fixture
def sample_cities(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, Any]]:
    """Два города с известными координатами для проверки порядка и фильтров."""
    cities: dict[str, dict[str, Any]] = {
        "alpha": _city(
            "Альфаград",
            [
                _branch("alpha_near", "ул. Ближняя, 1", lat=55.75, lon=37.62, landmark="центр"),
                _branch("alpha_far", "ул. Дальняя, 2", lat=55.80, lon=37.70),
                _branch("alpha_null", "ул. БезКоорд, 3", lat=None, lon=None),
                _branch(
                    "alpha_autodrome", "Автодром, 4", lat=55.751, lon=37.621, is_autodrome=True
                ),
                _branch(
                    "alpha_upcoming",
                    "ул. Скоро, 5",
                    lat=55.752,
                    lon=37.622,
                    hours="Скоро открытие",
                ),
            ],
        ),
        "beta": _city(
            "Бетаград",
            [
                _branch("beta_office", "пр. Другой, 10", lat=59.93, lon=30.33),
            ],
        ),
    }
    monkeypatch.setattr(lookup, "_cities", lambda: cities)
    return cities


def test_nearest_order_closest_first(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Ближайший филиал идёт первым, а не только длина списка верна."""
    result = nearest_branches(55.75, 37.62, limit=5, radius_km=50.0, city_slug="alpha")
    assert [item["слаг"] for item in result] == ["alpha_near", "alpha_far"]
    assert result[0]["расстояние"] < result[1]["расстояние"]


def test_nearest_skips_null_coords(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Филиал с lat/lon null в выдачу не попадает."""
    result = nearest_branches(55.75, 37.62, limit=10, radius_km=50.0, city_slug="alpha")
    slugs = [item["слаг"] for item in result]
    assert "alpha_null" not in slugs


def test_nearest_respects_radius(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Филиал за пределами radius_km не попадает."""
    result = nearest_branches(55.75, 37.62, limit=10, radius_km=1.0, city_slug="alpha")
    slugs = [item["слаг"] for item in result]
    assert "alpha_near" in slugs
    assert "alpha_far" not in slugs


def test_nearest_limit(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Параметр limit режет выдачу."""
    result = nearest_branches(55.75, 37.62, limit=1, radius_km=50.0, city_slug="alpha")
    assert len(result) == 1
    assert result[0]["слаг"] == "alpha_near"


def test_nearest_autodrome_filter(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Автодром отфильтрован по умолчанию и присутствует при include_autodromes."""
    without = nearest_branches(55.75, 37.62, limit=10, radius_km=50.0, city_slug="alpha")
    assert "alpha_autodrome" not in [item["слаг"] for item in without]
    with_auto = nearest_branches(
        55.75,
        37.62,
        limit=10,
        radius_km=50.0,
        city_slug="alpha",
        include_autodromes=True,
    )
    assert "alpha_autodrome" in [item["слаг"] for item in with_auto]


def test_nearest_upcoming_filter(sample_cities: dict[str, dict[str, Any]]) -> None:
    """«Скоро открытие» отфильтрован по умолчанию и присутствует при include_upcoming."""
    without = nearest_branches(55.75, 37.62, limit=10, radius_km=50.0, city_slug="alpha")
    assert "alpha_upcoming" not in [item["слаг"] for item in without]
    with_upcoming = nearest_branches(
        55.75,
        37.62,
        limit=10,
        radius_km=50.0,
        city_slug="alpha",
        include_upcoming=True,
    )
    assert "alpha_upcoming" in [item["слаг"] for item in with_upcoming]


def test_nearest_city_slug_scopes_search(sample_cities: dict[str, dict[str, Any]]) -> None:
    """city_slug не пускает филиалы других городов; без него — вся сеть."""
    scoped = nearest_branches(55.75, 37.62, limit=10, radius_km=5000.0, city_slug="alpha")
    assert all(item["город"] == "Альфаград" for item in scoped)
    assert "beta_office" not in [item["слаг"] for item in scoped]

    whole = nearest_branches(55.75, 37.62, limit=10, radius_km=5000.0)
    slugs = [item["слаг"] for item in whole]
    assert "alpha_near" in slugs
    assert "beta_office" in slugs


def test_nearest_empty_when_outside_radius(sample_cities: dict[str, dict[str, Any]]) -> None:
    """Пустой результат, когда в радиусе никого нет."""
    result = nearest_branches(0.0, 0.0, limit=5, radius_km=1.0)
    assert result == []


def test_city_name(sample_cities: dict[str, dict[str, Any]]) -> None:
    """city_name отдаёт название по слагу и None по мусорному слагу."""
    assert city_name("alpha") == "Альфаград"
    assert city_name("нет-такого") is None
