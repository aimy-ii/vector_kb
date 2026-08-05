"""Тесты DaData-геокодеров (Подсказки и Cleaner) без сети."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from app.core.config import settings
from app.services.directory_service.geocoders.dadata import (
    CLEAN_ADDRESS_URL,
    SUGGEST_ADDRESS_URL,
    DadataCleanerGeocoder,
    DadataSuggestionsGeocoder,
)

#: Явно тестовые заглушки — не настоящие ключи.
TEST_API_KEY = "test-dadata-api-key"
TEST_SECRET_KEY = "test-dadata-secret-key"


@pytest.fixture
def dadata_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подставляет только API-ключ (для Подсказок)."""
    monkeypatch.setattr(settings, "dadata_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "dadata_secret_key", "")


@pytest.fixture
def dadata_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подставляет оба ключа (для Cleaner)."""
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


def _suggest_payload(
    *,
    geo_lat: Any = "59.934280",
    geo_lon: Any = "30.335099",
    qc_geo: Any = 0,
) -> dict[str, Any]:
    """Собирает ответ API подсказок с одной suggestion."""
    return {"suggestions": [{"data": {"geo_lat": geo_lat, "geo_lon": geo_lon, "qc_geo": qc_geo}}]}


# --- Подсказки ---


def test_suggestions_returns_floats(monkeypatch: pytest.MonkeyPatch, dadata_api_key: None) -> None:
    """Нормальный ответ Подсказок даёт пару float из строковых координат."""
    geocoder = DadataSuggestionsGeocoder()
    response = _mock_response(payload=_suggest_payload())
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("Невский проспект, 28") == (
        59.934280,
        30.335099,
    )
    assert geocoder.last_qc_geo == 0


def test_suggestions_empty_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Пустой suggestions даёт None."""
    geocoder = DadataSuggestionsGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(payload={"suggestions": []}))
    assert geocoder.geocode_sync("нигде") is None


def test_suggestions_missing_coords_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Отсутствующие координаты в data дают None."""
    geocoder = DadataSuggestionsGeocoder()
    payload = {"suggestions": [{"data": {"qc_geo": 0}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(payload=payload))
    assert geocoder.geocode_sync("адрес") is None


def test_suggestions_null_coords_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """null в geo_lat/geo_lon даёт None."""
    geocoder = DadataSuggestionsGeocoder()
    response = _mock_response(payload=_suggest_payload(geo_lat=None, geo_lon=None, qc_geo=0))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") is None


@pytest.mark.parametrize("qc_geo", [0, 1, 2])
def test_suggestions_qc_geo_acceptable(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None, qc_geo: int
) -> None:
    """qc_geo 0, 1, 2 у Подсказок принимаются."""
    geocoder = DadataSuggestionsGeocoder()
    response = _mock_response(
        payload=_suggest_payload(geo_lat="55.75", geo_lon="37.62", qc_geo=qc_geo)
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") == (55.75, 37.62)
    assert geocoder.last_qc_geo == qc_geo


@pytest.mark.parametrize("qc_geo", [3, 4])
def test_suggestions_qc_geo_too_coarse(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None, qc_geo: int
) -> None:
    """qc_geo 3 и 4 у Подсказок отбраковываются."""
    geocoder = DadataSuggestionsGeocoder()
    response = _mock_response(
        payload=_suggest_payload(geo_lat="55.75", geo_lon="37.62", qc_geo=qc_geo)
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("город") is None
    assert geocoder.last_qc_geo is None


def test_suggestions_request_shape(monkeypatch: pytest.MonkeyPatch, dadata_api_key: None) -> None:
    """В запрос уходят query/count=1 и Authorization, без X-Secret и без locations."""
    geocoder = DadataSuggestionsGeocoder()
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs.get("headers")
        return _mock_response(payload=_suggest_payload(geo_lat="1.0", geo_lon="2.0"))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("Тестовый адрес") == (1.0, 2.0)
    assert captured["url"] == SUGGEST_ADDRESS_URL
    assert captured["json"] == {"query": "Тестовый адрес", "count": 1}
    assert "locations" not in captured["json"]
    assert "restrict_value" not in captured["json"]
    headers = captured["headers"]
    assert headers["Authorization"] == f"Token {TEST_API_KEY}"
    assert "X-Secret" not in headers
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


def test_suggestions_with_city_adds_locations(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """При переданном городе в тело уходят locations и restrict_value."""
    geocoder = DadataSuggestionsGeocoder()
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured["json"] = kwargs.get("json")
        return _mock_response(payload=_suggest_payload(geo_lat="1.0", geo_lon="2.0"))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("ул. Славы, д. 12", city="Красноярск") == (1.0, 2.0)
    assert captured["json"] == {
        "query": "ул. Славы, д. 12",
        "count": 1,
        "locations": [{"city": "Красноярск"}],
        "restrict_value": True,
    }


def test_suggestions_retries_without_city_on_empty(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Пустой ответ с ограничением → ровно один повтор без locations, город в конце."""
    geocoder = DadataSuggestionsGeocoder()
    bodies: list[Any] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        body = kwargs.get("json")
        bodies.append(body)
        if body and "locations" in body:
            return _mock_response(payload={"suggestions": []})
        return _mock_response(payload=_suggest_payload(geo_lat="43.1", geo_lon="131.9"))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("Владивосток, ул. Русская, 9Б", city="Владивосток") == (
        43.1,
        131.9,
    )
    assert len(bodies) == 2
    assert bodies[0] == {
        "query": "Владивосток, ул. Русская, 9Б",
        "count": 1,
        "locations": [{"city": "Владивосток"}],
        "restrict_value": True,
    }
    assert bodies[1] == {"query": "ул. Русская, 9Б, Владивосток", "count": 1}
    assert "locations" not in bodies[1]
    assert "restrict_value" not in bodies[1]


def test_suggestions_retries_without_city_on_coarse_qc(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Грубый qc_geo с ограничением → повтор без locations."""
    geocoder = DadataSuggestionsGeocoder()
    bodies: list[Any] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        body = kwargs.get("json")
        bodies.append(body)
        if body and "locations" in body:
            return _mock_response(payload=_suggest_payload(qc_geo=4))
        return _mock_response(payload=_suggest_payload(geo_lat="55.0", geo_lon="37.0", qc_geo=0))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("Адлер, ул. Кирова, 23", city="Адлер") == (55.0, 37.0)
    assert len(bodies) == 2
    assert bodies[1]["query"] == "ул. Кирова, 23, Адлер"
    assert "locations" not in bodies[1]


def test_suggestions_no_retry_when_first_ok(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Удачный первый запрос с городом не порождает второй."""
    geocoder = DadataSuggestionsGeocoder()
    calls = {"n": 0}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        calls["n"] += 1
        return _mock_response(payload=_suggest_payload(geo_lat="1.0", geo_lon="2.0"))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("ул. Славы, 12", city="Красноярск") == (1.0, 2.0)
    assert calls["n"] == 1


def test_suggestions_retry_exactly_once_when_both_fail(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Оба запроса пустые → None и ровно два обращения."""
    geocoder = DadataSuggestionsGeocoder()
    calls = {"n": 0}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        calls["n"] += 1
        return _mock_response(payload={"suggestions": []})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("нигде", city="Омск") is None
    assert calls["n"] == 2


def test_suggestions_without_city_omits_locations(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Без города поля locations и restrict_value не добавляются."""
    geocoder = DadataSuggestionsGeocoder()
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured["json"] = kwargs.get("json")
        return _mock_response(payload=_suggest_payload(geo_lat="1.0", geo_lon="2.0"))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("ул. Славы, д. 12", city=None) == (1.0, 2.0)
    assert captured["json"] == {"query": "ул. Славы, д. 12", "count": 1}


def test_suggestions_build_query_city_first(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Подсказки ставят город впереди адреса."""
    geocoder = DadataSuggestionsGeocoder()
    assert geocoder.build_query("ул. Славы, 12", "Красноярск") == ("Красноярск, ул. Славы, 12")
    assert geocoder.build_query("ул. Славы, 12", None) == "ул. Славы, 12"


def test_cleaner_build_query_city_first(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """Cleaner ставит город впереди адреса."""
    geocoder = DadataCleanerGeocoder()
    assert geocoder.build_query("ул. Славы, 12", "Красноярск") == ("Красноярск, ул. Славы, 12")
    assert geocoder.build_query("ул. Славы, 12", None) == "ул. Славы, 12"


def test_suggestions_creates_with_api_key_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Подсказки создаются при одном DADATA_API_KEY без секрета."""
    monkeypatch.setattr(settings, "dadata_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    geocoder = DadataSuggestionsGeocoder()
    assert geocoder is not None


def test_suggestions_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без API-ключа Подсказки бросают RuntimeError."""
    monkeypatch.setattr(settings, "dadata_api_key", "")
    with pytest.raises(RuntimeError, match="DADATA_API_KEY"):
        DadataSuggestionsGeocoder()


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_suggestions_http_errors_return_none(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None, status_code: int
) -> None:
    """HTTP-ошибки Подсказок дают None без исключения наружу."""
    geocoder = DadataSuggestionsGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(status_code=status_code))
    assert geocoder.geocode_sync("адрес") is None


def test_suggestions_network_error_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_api_key: None
) -> None:
    """Сетевая ошибка Подсказок даёт None."""
    geocoder = DadataSuggestionsGeocoder()

    def boom(*args: Any, **kwargs: Any) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    assert geocoder.geocode_sync("адрес") is None


# --- Cleaner ---


def test_cleaner_returns_floats(monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None) -> None:
    """Нормальный ответ Cleaner даёт пару float из строковых координат."""
    geocoder = DadataCleanerGeocoder()
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
def test_cleaner_qc_geo_acceptable(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None, qc_geo: int
) -> None:
    """qc_geo 0, 1, 2 у Cleaner принимаются."""
    geocoder = DadataCleanerGeocoder()
    response = _mock_response(payload=[{"geo_lat": "55.75", "geo_lon": "37.62", "qc_geo": qc_geo}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") == (55.75, 37.62)


@pytest.mark.parametrize("qc_geo", [3, 4])
def test_cleaner_qc_geo_too_coarse(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None, qc_geo: int
) -> None:
    """qc_geo 3 и 4 у Cleaner отбраковываются."""
    geocoder = DadataCleanerGeocoder()
    response = _mock_response(payload=[{"geo_lat": "55.75", "geo_lon": "37.62", "qc_geo": qc_geo}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("город") is None


def test_cleaner_empty_array_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """Пустой массив Cleaner даёт None."""
    geocoder = DadataCleanerGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(payload=[]))
    assert geocoder.geocode_sync("нигде") is None


def test_cleaner_missing_coords_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """Отсутствующие координаты Cleaner дают None."""
    geocoder = DadataCleanerGeocoder()
    response = _mock_response(payload=[{"qc_geo": 0}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") is None


def test_cleaner_null_coords_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """null в координатах Cleaner даёт None."""
    geocoder = DadataCleanerGeocoder()
    response = _mock_response(payload=[{"geo_lat": None, "geo_lon": None, "qc_geo": 0}])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    assert geocoder.geocode_sync("адрес") is None


def test_cleaner_requires_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без ключей Cleaner — RuntimeError с именами переменных."""
    monkeypatch.setattr(settings, "dadata_api_key", "")
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    with pytest.raises(RuntimeError, match="DADATA_API_KEY") as exc_info:
        DadataCleanerGeocoder()
    assert "DADATA_SECRET_KEY" in str(exc_info.value)


def test_cleaner_requires_secret_when_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Одного API-ключа для Cleaner недостаточно."""
    monkeypatch.setattr(settings, "dadata_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    with pytest.raises(RuntimeError, match="DADATA_SECRET_KEY"):
        DadataCleanerGeocoder()


def test_cleaner_request_headers_and_body(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """В запрос Cleaner уходят оба заголовка и тело-массив."""
    geocoder = DadataCleanerGeocoder()
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


def test_cleaner_accepts_city_argument(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """Cleaner принимает аргумент city и не ломается; в теле его нет."""
    geocoder = DadataCleanerGeocoder()
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured["json"] = kwargs.get("json")
        return _mock_response(payload=[{"geo_lat": "1.0", "geo_lon": "2.0", "qc_geo": 0}])

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geocoder.geocode_sync("Тестовый адрес", city="Томск") == (1.0, 2.0)
    assert captured["json"] == ["Тестовый адрес"]


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_cleaner_http_errors_return_none(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None, status_code: int
) -> None:
    """HTTP-ошибки Cleaner дают None без исключения наружу."""
    geocoder = DadataCleanerGeocoder()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _mock_response(status_code=status_code))
    assert geocoder.geocode_sync("адрес") is None


def test_cleaner_network_error_returns_none(
    monkeypatch: pytest.MonkeyPatch, dadata_both_keys: None
) -> None:
    """Сетевая ошибка Cleaner даёт None."""
    geocoder = DadataCleanerGeocoder()

    def boom(*args: Any, **kwargs: Any) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    assert geocoder.geocode_sync("адрес") is None
