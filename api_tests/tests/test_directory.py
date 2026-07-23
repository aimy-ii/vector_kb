"""Чёрный ящик: справочник и живость сервиса."""

from __future__ import annotations

import pytest

from utils.api_client import APIClient


@pytest.mark.requires_service
class TestHealth:
    """Проверки живости поднятого сервиса."""

    def test_health_returns_cities(self, public_client: APIClient) -> None:
        """GET /api/health отдаёт ненулевое число городов."""
        response = public_client.get("/api/health")
        assert response.status_code == 200, response.text
        assert response.json()["cities_count"] > 0


@pytest.mark.requires_service
class TestDirectory:
    """Проверки справочника через HTTP."""

    def test_cities_enum_nonempty(self, public_client: APIClient) -> None:
        """GET /api/cities/enum не пуст."""
        response = public_client.get("/api/cities/enum")
        assert response.status_code == 200, response.text
        assert response.json()

    def test_resolve_piter(self, public_client: APIClient) -> None:
        """Разговорное «Питер» резолвится в sankt-peterburg."""
        response = public_client.get("/api/cities/resolve", params={"text": "Питер"})
        assert response.status_code == 200, response.text
        assert response.json()["slug"] == "sankt-peterburg"

    def test_branch_detail(self, public_client: APIClient) -> None:
        """Известный филиал отдаёт адрес."""
        response = public_client.get("/api/branches/perm_chernyshevskogo")
        assert response.status_code == 200, response.text
        assert response.json()["address"]
