"""Тесты схем: валидация и отсутствие полей с ценой."""

from __future__ import annotations

import json

from app.schemas.directory import BranchDetail, CityDetail
from app.services import directory_api
from app.services.directory_service import city_enum


def test_city_detail_schema_has_no_price_fields() -> None:
    """В схеме и примере CityDetail нет полей с ценой."""
    schema = CityDetail.model_json_schema()
    blob = json.dumps(schema, ensure_ascii=False).lower()
    assert "price" not in blob
    assert "цена" not in blob
    assert "₽" not in blob
    assert "tariff" not in blob


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


def test_api_city_detail_has_no_price_leak() -> None:
    """Ответ city_detail не содержит цену, ₽ и слово «цена»."""
    for slug in city_enum():
        detail = directory_api.city_detail(slug)
        assert detail is not None
        blob = detail.model_dump_json().lower()
        assert "цена" not in blob
        assert "₽" not in blob
        assert "price" not in blob
