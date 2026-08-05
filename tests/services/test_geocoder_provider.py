"""Тесты выбора провайдера геокодера."""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.services.directory_service.geocoders import _PROVIDERS, build_geocoder, geocoder
from app.services.directory_service.geocoders.dadata import (
    DadataCleanerGeocoder,
    DadataSuggestionsGeocoder,
)
from app.services.directory_service.geocoders.nominatim import NominatimGeocoder


@pytest.fixture(autouse=True)
def _clear_geocoder_cache() -> None:
    """Сбрасывает кэш build_geocoder между тестами."""
    build_geocoder.cache_clear()
    yield
    build_geocoder.cache_clear()


def test_providers_registry_has_three_keys() -> None:
    """В реестре три провайдера: dadata, dadata_cleaner, nominatim."""
    assert set(_PROVIDERS) == {"dadata", "dadata_cleaner", "nominatim"}


def test_build_geocoder_nominatim(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEOCODER_PROVIDER=nominatim даёт NominatimGeocoder."""
    monkeypatch.setattr(settings, "geocoder_provider", "nominatim")
    monkeypatch.setattr(settings, "geocoder_contact", "geocoder-tests@localhost")
    assert isinstance(build_geocoder(), NominatimGeocoder)


def test_build_geocoder_dadata_suggestions(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEOCODER_PROVIDER=dadata даёт DadataSuggestionsGeocoder."""
    monkeypatch.setattr(settings, "geocoder_provider", "dadata")
    monkeypatch.setattr(settings, "dadata_api_key", "test-dadata-api-key")
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    assert isinstance(build_geocoder(), DadataSuggestionsGeocoder)


def test_build_geocoder_dadata_cleaner(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEOCODER_PROVIDER=dadata_cleaner даёт DadataCleanerGeocoder."""
    monkeypatch.setattr(settings, "geocoder_provider", "dadata_cleaner")
    monkeypatch.setattr(settings, "dadata_api_key", "test-dadata-api-key")
    monkeypatch.setattr(settings, "dadata_secret_key", "test-dadata-secret-key")
    assert isinstance(build_geocoder(), DadataCleanerGeocoder)


def test_build_geocoder_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Неизвестное значение бросает RuntimeError с перечислением доступных."""
    monkeypatch.setattr(settings, "geocoder_provider", "yandex")
    with pytest.raises(RuntimeError, match="Неизвестный GEOCODER_PROVIDER") as exc:
        build_geocoder()
    message = str(exc.value)
    assert "dadata" in message
    assert "dadata_cleaner" in message
    assert "nominatim" in message


def test_geocoders_import_without_keys_does_not_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Модуль geocoders без ключей не падает — клиент создаётся лениво."""
    monkeypatch.setattr(settings, "geocoder_provider", "dadata")
    monkeypatch.setattr(settings, "dadata_api_key", "")
    monkeypatch.setattr(settings, "dadata_secret_key", "")
    assert geocoder is not None
    assert hasattr(geocoder, "geocode")
    assert build_geocoder.cache_info().currsize == 0
    with pytest.raises(RuntimeError, match="DADATA_API_KEY"):
        build_geocoder()
