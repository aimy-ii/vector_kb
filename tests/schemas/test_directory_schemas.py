"""Тесты схем: валидация и поле цены с оговоркой."""

from __future__ import annotations

from app.constants.directory import PRICE_DISCLAIMER, PRICE_UNKNOWN
from app.schemas.directory import BranchDetail, BranchNearby, CityDetail, GeocodeResult, PriceInfo
from app.services.directory_service import api as directory_api
from app.services.directory_service import city_enum


def test_city_detail_schema_has_price_field() -> None:
    """В схеме CityDetail есть поле price."""
    schema = CityDetail.model_json_schema()
    assert "price" in schema["properties"]
    price_ref = schema["properties"]["price"]
    assert "$ref" in price_ref or "properties" in price_ref


def test_branch_detail_place_type_and_status() -> None:
    """BranchDetail принимает русские значения типа и статуса."""
    detail = BranchDetail(
        slug="perm_test",
        city="Пермь",
        address="ул. Тестовая, 1",
        place_type="учебный офис",
        status="работает",
    )
    assert detail.place_type == "учебный офис"
    assert detail.status == "работает"


def test_branch_nearby_and_geocode_result_fields() -> None:
    """BranchNearby и GeocodeResult содержат ожидаемые поля."""
    nearby = BranchNearby(
        slug="krasnoyarsk_slavy",
        city="Красноярск",
        address="ул. Славы, 12",
        landmark=None,
        distance_km=0.42,
    )
    assert nearby.slug == "krasnoyarsk_slavy"
    assert nearby.distance_km == 0.42
    nearby_schema = BranchNearby.model_json_schema()
    for key in ("slug", "city", "address", "landmark", "distance_km"):
        assert key in nearby_schema["properties"]

    found = GeocodeResult(text="Купчино", lat=59.85, lon=30.35, found=True)
    assert found.found is True
    assert found.lat == 59.85
    missing = GeocodeResult(text="нигде", lat=None, lon=None, found=False)
    assert missing.found is False
    geocode_schema = GeocodeResult.model_json_schema()
    for key in ("text", "lat", "lon", "found"):
        assert key in geocode_schema["properties"]


def test_api_city_detail_price_with_disclaimer() -> None:
    """У города с ценой — сумма, is_from из тарифа и оговорка PRICE_DISCLAIMER."""
    from app.services.directory_service.store import directory_store

    priced: list = []
    for slug in city_enum():
        detail = directory_api.city_detail(slug)
        assert detail is not None
        if detail.price.amount is not None:
            priced.append((slug, detail))
    assert priced
    for slug, detail in priced:
        assert isinstance(detail.price.amount, int)
        raw_items = directory_store.cities[slug].get("tariffs", {}).get("items", [])
        first = next(i for i in raw_items if isinstance(i, dict) and i.get("price") is not None)
        expected_is_from = (
            True if first.get("price_is_from") is None else bool(first["price_is_from"])
        )
        assert detail.price.is_from is expected_is_from
        assert detail.price.reliable is False
        assert detail.price.note == PRICE_DISCLAIMER


def test_api_city_detail_price_unknown() -> None:
    """Пустой раздел тарифов даёт amount=None и note=PRICE_UNKNOWN."""
    for empty in (None, {}, {"items": []}, {"items": [{"name": "без цены", "price": None}]}):
        info = directory_api.build_price_info(empty)
        assert info.amount is None
        assert info.note == PRICE_UNKNOWN
        assert info.reliable is False


def test_all_cities_price_not_reliable() -> None:
    """Ни один из 41 города не помечен как подтверждённый прайс."""
    details = [directory_api.city_detail(slug) for slug in city_enum()]
    assert len(details) == 41
    for detail in details:
        assert detail is not None
        assert detail.price.reliable is False


def test_price_info_requires_note() -> None:
    """PriceInfo без note невалиден — суммы без оговорки быть не может."""
    try:
        PriceInfo(amount=21950, is_from=True, reliable=False)  # type: ignore[call-arg]
    except Exception:
        return
    raise AssertionError("PriceInfo должен требовать note")
