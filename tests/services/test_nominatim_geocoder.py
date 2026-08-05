"""Тесты Nominatim-геокодера без сети."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.core.config import settings
from app.services.directory_service.geocoders.nominatim import (
    NominatimGeocoder,
    is_too_coarse,
)
from geopy.exc import GeocoderInsufficientPrivileges, GeocoderServiceError

#: Явно тестовый контакт — не реальный адрес.
TEST_CONTACT = "geocoder-tests@localhost"


@pytest.fixture
def geocoder_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подставляет непустой контакт в настройки перед созданием клиента."""
    monkeypatch.setattr(settings, "geocoder_contact", TEST_CONTACT)


def test_is_too_coarse_district_bbox_passes() -> None:
    """Рамка района (доли градуса) проходит."""
    raw = {"boundingbox": ["59.80", "59.95", "30.20", "30.45"]}
    assert is_too_coarse(raw) is False


def test_is_too_coarse_region_bbox_rejected() -> None:
    """Рамка в несколько градусов отбраковывается."""
    raw = {"boundingbox": ["55.0", "60.0", "30.0", "40.0"]}
    assert is_too_coarse(raw) is True


def test_is_too_coarse_missing_or_broken_bbox() -> None:
    """Отсутствующая и битая рамка не роняют разбор."""
    assert is_too_coarse({}) is False
    assert is_too_coarse({"boundingbox": ["a", "b", "c", "d"]}) is False
    assert is_too_coarse({"boundingbox": [1, 2]}) is False
    assert is_too_coarse({"boundingbox": "not-a-list"}) is False


def test_geocode_sync_returns_point(
    monkeypatch: pytest.MonkeyPatch, geocoder_contact: None
) -> None:
    """Нормальный ответ клиента даёт пару чисел."""
    geocoder = NominatimGeocoder()
    location = SimpleNamespace(
        latitude=59.85,
        longitude=30.35,
        raw={"boundingbox": ["59.80", "59.90", "30.30", "30.40"]},
    )
    monkeypatch.setattr(geocoder._client, "geocode", lambda *a, **k: location)
    assert geocoder.geocode_sync("Купчино, Санкт-Петербург") == (59.85, 30.35)


def test_geocode_sync_none_location(
    monkeypatch: pytest.MonkeyPatch, geocoder_contact: None
) -> None:
    """Пустой ответ провайдера даёт None."""
    geocoder = NominatimGeocoder()
    monkeypatch.setattr(geocoder._client, "geocode", lambda *a, **k: None)
    assert geocoder.geocode_sync("нигде") is None


def test_geocode_sync_too_coarse(monkeypatch: pytest.MonkeyPatch, geocoder_contact: None) -> None:
    """Слишком крупный объект отбраковывается."""
    geocoder = NominatimGeocoder()
    location = SimpleNamespace(
        latitude=55.0,
        longitude=37.0,
        raw={"boundingbox": ["50.0", "60.0", "30.0", "45.0"]},
    )
    monkeypatch.setattr(geocoder._client, "geocode", lambda *a, **k: location)
    assert geocoder.geocode_sync("Россия") is None


def test_geocode_sync_service_error(
    monkeypatch: pytest.MonkeyPatch, geocoder_contact: None
) -> None:
    """GeocoderServiceError даёт None, а не исключение наружу."""
    geocoder = NominatimGeocoder()

    def boom(*args: Any, **kwargs: Any) -> None:
        raise GeocoderServiceError("down")

    monkeypatch.setattr(geocoder._client, "geocode", boom)
    assert geocoder.geocode_sync("Купчино") is None


def test_geocode_sync_insufficient_privileges(
    monkeypatch: pytest.MonkeyPatch, geocoder_contact: None
) -> None:
    """GeocoderInsufficientPrivileges возвращает None и не роняет процесс."""
    geocoder = NominatimGeocoder()

    def boom(*args: Any, **kwargs: Any) -> None:
        raise GeocoderInsufficientPrivileges("403")

    monkeypatch.setattr(geocoder._client, "geocode", boom)
    assert geocoder.geocode_sync("Купчино") is None


def test_nominatim_requires_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пустой geocoder_contact даёт RuntimeError с упоминанием GEOCODER_CONTACT."""
    monkeypatch.setattr(settings, "geocoder_contact", "")
    with pytest.raises(RuntimeError, match="GEOCODER_CONTACT"):
        NominatimGeocoder()


def test_nominatim_creates_with_contact(
    monkeypatch: pytest.MonkeyPatch, geocoder_contact: None
) -> None:
    """С заполненным контактом клиент создаётся без ошибки."""
    geocoder = NominatimGeocoder()
    assert geocoder._client is not None
