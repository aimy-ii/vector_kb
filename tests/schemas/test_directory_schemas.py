"""Тесты схем: валидация и поле цены с оговоркой."""

from __future__ import annotations

from app.constants.directory import PRICE_DISCLAIMER, PRICE_UNKNOWN
from app.schemas.directory import BranchDetail, CityDetail, PriceInfo
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


def test_api_city_detail_price_with_disclaimer() -> None:
    """У города с ценой — сумма, is_from и оговорка PRICE_DISCLAIMER."""
    priced: list = []
    for slug in city_enum():
        detail = directory_api.city_detail(slug)
        assert detail is not None
        if detail.price.amount is not None:
            priced.append(detail)
    assert priced
    for detail in priced:
        assert isinstance(detail.price.amount, int)
        assert detail.price.is_from is True
        assert detail.price.reliable is False
        assert detail.price.note == PRICE_DISCLAIMER


def test_api_city_detail_price_unknown() -> None:
    """У города без цены amount=None и note=PRICE_UNKNOWN."""
    unknown: list = []
    for slug in city_enum():
        detail = directory_api.city_detail(slug)
        assert detail is not None
        if detail.price.amount is None:
            unknown.append(detail)
    assert unknown
    for detail in unknown:
        assert detail.price.amount is None
        assert detail.price.note == PRICE_UNKNOWN
        assert detail.price.reliable is False


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
