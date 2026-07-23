"""Тесты HTTP-эндпоинтов через TestClient."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.constants.parsing import JobStatus
from app.services.directory_service import city_enum, list_cities
from app.services.parsing_service import jobs as jobs_service
from app.services.parsing_service.jobs import ParseJob
from fastapi.testclient import TestClient


def _blob(response) -> str:
    """Тело ответа одной строкой в нижнем регистре."""
    return json.dumps(response.json(), ensure_ascii=False).lower()


def test_health_ok(client: TestClient) -> None:
    """GET /api/health отвечает 200 и показывает ненулевое число городов."""
    response = client.get("/api/health")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ok"
    assert data["cities_count"] > 0
    assert data["branches_count"] > 0
    assert data["loaded_at"] is not None


def test_cities_and_enum_agree(client: TestClient) -> None:
    """GET /api/cities и /api/cities/enum согласованы между собой."""
    cities = client.get("/api/cities")
    enum_resp = client.get("/api/cities/enum")
    assert cities.status_code == 200, cities.text
    assert enum_resp.status_code == 200, enum_resp.text
    slugs = [item["slug"] for item in cities.json()]
    assert slugs == enum_resp.json()


def test_city_detail_found_and_missing(client: TestClient) -> None:
    """Существующий слаг — 200, выдуманный — 404."""
    slug = city_enum()[0]
    ok = client.get(f"/api/cities/{slug}")
    assert ok.status_code == 200, ok.text
    missing = client.get("/api/cities/net-takogo-goroda")
    assert missing.status_code == 404, missing.text
    assert "не найден" in missing.json()["detail"].lower()


def test_branches_enum_prefixed(client: TestClient) -> None:
    """Слаги филиалов начинаются со слага города."""
    slug = city_enum()[0]
    response = client.get(f"/api/cities/{slug}/branches/enum")
    assert response.status_code == 200, response.text
    branches = response.json()
    assert branches
    for branch_slug in branches:
        assert branch_slug.startswith(slug)


def test_branch_detail(client: TestClient) -> None:
    """GET /api/branches/{slug} даёт адрес, тип и статус."""
    city = list_cities()[0]["слаг"]
    branch_slug = client.get(f"/api/cities/{city}/branches/enum").json()[0]
    response = client.get(f"/api/branches/{branch_slug}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["address"]
    assert data["place_type"] in ("учебный офис", "автодром")
    assert data["status"] in ("работает", "скоро открытие")


def test_resolve_piter_and_spb(client: TestClient) -> None:
    """Питер и спб дают один слаг."""
    piter = client.get("/api/cities/resolve", params={"text": "Питер"})
    spb = client.get("/api/cities/resolve", params={"text": "спб"})
    assert piter.status_code == 200, piter.text
    assert spb.status_code == 200, spb.text
    assert piter.json()["slug"] == spb.json()["slug"] == "sankt-peterburg"


def test_resolve_moscow_null(client: TestClient) -> None:
    """Москва — 200 и slug: null."""
    response = client.get("/api/cities/resolve", params={"text": "Москва"})
    assert response.status_code == 200, response.text
    assert response.json()["slug"] is None


def test_no_price_in_api_responses(client: TestClient) -> None:
    """Ни один ответ справочника не содержит цену, ₽ и слово «цена»."""
    paths = [
        "/api/cities",
        "/api/cities/enum",
        f"/api/cities/{city_enum()[0]}",
        f"/api/cities/{city_enum()[0]}/branches",
    ]
    city = list_cities()[0]["слаг"]
    branch = client.get(f"/api/cities/{city}/branches/enum").json()[0]
    paths.append(f"/api/branches/{branch}")
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, response.text
        blob = _blob(response)
        assert "цена" not in blob
        assert "₽" not in blob
        assert "price" not in blob


def test_parse_conflict_when_active(client: TestClient) -> None:
    """Второй POST /api/parse при активной задаче отдаёт 409."""
    active = ParseJob(job_id="busyjob", status=JobStatus.RUNNING)
    jobs_service._jobs[active.job_id] = active
    jobs_service._active_job_id = active.job_id

    with patch.object(
        jobs_service, "start_job", side_effect=jobs_service.JobConflictError("busyjob")
    ):
        response = client.post("/api/parse", json={})
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["job_id"] == "busyjob"


def test_reload_returns_cities_count(client: TestClient) -> None:
    """POST /api/reload возвращает число загруженных городов."""
    response = client.post("/api/reload")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cities_count"] > 0
    assert data["branches_count"] > 0


def test_city_and_branch_slugs_do_not_collide(client: TestClient) -> None:
    """Слаги городов и филиалов не пересекаются."""
    cities = set(client.get("/api/cities/enum").json())
    branches: set[str] = set()
    for slug in cities:
        branches.update(client.get(f"/api/cities/{slug}/branches/enum").json())
    assert cities.isdisjoint(branches)
