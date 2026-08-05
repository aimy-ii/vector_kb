"""Тесты DaData-геокодера без сети."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from app.core.config import settings
from app.services.directory_service.geocoders.dadata import (
    CLEAN_ADDRESS_URL,
    DadataGeocoder,
)

#: Явно тестовые заглушки — не настоящие ключи.
TEST_API_KEY = "test-dadata-api-key"
TEST_SECRET_KEY = "test-dadata-secret-key"


@pytest.fixture
def dadata_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подставляет тестовые ключи DaData в настройки."""
    monkeypatch.setattr(settings, "dadata_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "dadata_secret_key", TEST_SECRET_KEY)


def _mock_response(
    *,
    status_code: int = 200,
    payload: Any = None,
) -> MagicMock:
    """Собирает заглушку ответа httpx."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_geocode_sync_returns_floats_from_strings(
    monkeypatch: pytest.MonkeyPatch, dadata_keys: None
) -> None:
    """Нормальный ответ даёт пару float из строковых geo_lat/geo_lon."""
    geocoder = DadataGeocoder()
    response = _mock_response(
        payload=[{"geo_lat": "59.934280", "geo_lon": "30.335099", "qc_geo": 0}]
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("Невский проспект, 28") == (
        59.934280,
        30.335099,
    )
    assert geocoder.last_qc_geo == 0


@pytest.mark.parametrize("qc_geo", [0, 1, 2])
def test_qc_geo_acceptable_passes(
    monkeypatch: pytest.MonkeyPatch, dadata_keys: None, qc_geo: int
) -> None:
    """qc_geo 0, 1, 2 принимаются."""
    geocoder = DadataGeocoder()
    response = _mock_response(payload=[{"geo_lat": "55.75", "geo_lon": "37.62", "qc_geo": qc_geo}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") == (55.75, 37.62)
    assert geocoder.last_qc_geo == qc_geo


@pytest.mark.parametrize("qc_geo", [3, 4])
def test_qc_geo_too_coarse_rejected(
    monkeypatch: pytest.MonkeyPatch, dadata_keys: None, qc_geo: int
) -> None:
    """qc_geo 3 и 4 отбраковываются."""
    geocoder = DadataGeocoder()
    response = _mock_response(payload=[{"geo_lat": "55.75", "geo_lon": "37.62", "qc_geo": qc_geo}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("город") is None
    assert geocoder.last_qc_geo is None


def test_empty_array_returns_none(monkeypatch: pytest.MonkeyPatch, dadata_keys: None) -> None:
    """Пустой массив ответа даёт None."""
    geocoder = DadataGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(payload=[]))
    assert geocoder.geocode_sync("нигде") is None


def test_missing_coords_returns_none(monkeypatch: pytest.MonkeyPatch, dadata_keys: None) -> None:
    """Отсутствующие координаты дают None."""
    geocoder = DadataGeocoder()
    response = _mock_response(payload=[{"qc_geo": 0}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") is None


def test_null_coords_returns_none(monkeypatch: pytest.MonkeyPatch, dadata_keys: None) -> None:
    """null в geo_lat/geo_lon даёт None."""
    geocoder = DadataGeocoder()
    response = _mock_response(payload=[{"geo_lat": None, "geo_lon": None, "qc_geo": 0}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") is None


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_http_errors_return_none(
    monkeypatch: pytest.MonkeyPatch, dadata_keys: None, status_code: int
) -> None:
    """HTTP-ошибки дают None, исключение наружу не уходит."""
    geocoder = DadataGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(status_code=status_code))
    assert geocoder.geocode_sync("адрес") is None


def test_network_error_returns_none(monkeypatch: pytest.MonkeyPatch, dadata_keys: None) -> None:
    """Сетевая ошибка даёт None без исключения наружу."""
    geocoder = DadataGeocoder()

    def boom(*args: Any, **kwargs: Any) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    assert geocoder.geocode_sync("адрес") is None


def test_requires_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без ключей — RuntimeError с именами переменных окружения."""
    monkeypatch.setattr(settings, "dadata_api_key", "")
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    with pytest.raises(RuntimeError, match="DADATA_API_KEY") as exc_info:
        DadataGeocoder()
    assert "DADATA_SECRET_KEY" in str(exc_info.value)


def test_requires_secret_when_api_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Одного API-ключа недостаточно."""
    monkeypatch.setattr(settings, "dadata_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    with pytest.raises(RuntimeError, match="DADATA_SECRET_KEY"):
        DadataGeocoder()


def test_request_headers_and_body(monkeypatch: pytest.MonkeyPatch, dadata_keys: None) -> None:
    """В запрос уходят оба заголовка авторизации и тело — массив из одной строки."""
    geocoder = DadataGeocoder()
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs.get("headers")
        return _mock_response(payload=[{"geo_lat": "1.0", "geo_lon": "2.0", "qc_geo": 1}])

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("Тестовый адрес") == (1.0, 2.0)
    assert captured["url"] == CLEAN_ADDRESS_URL
    assert captured["json"] == ["Тестовый адрес"]
    headers = captured["headers"]
    assert headers["Authorization"] == f"Token {TEST_API_KEY}"
    assert headers["X-Secret"] == TEST_SECRET_KEY
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
