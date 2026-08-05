"""Тесты HTTP-эндпоинтов через TestClient."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.constants.parsing import JobStatus
from app.services.directory_service import city_enum, list_cities
from app.services.parsing_service import jobs as jobs_service
from app.services.parsing_service.jobs import ParseJob
from fastapi.testclient import TestClient


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


def test_city_detail_price_always_has_note(client: TestClient) -> None:
    """Ответ /api/cities/{slug} содержит цену и оговорку одновременно."""
    from app.constants.directory import PRICE_DISCLAIMER, PRICE_UNKNOWN
    from app.services.directory_service.store import directory_store

    for slug in city_enum():
        response = client.get(f"/api/cities/{slug}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "price" in data
        price = data["price"]
        assert "note" in price
        assert price["note"]
        assert price["reliable"] is False
        if price["amount"] is None:
            assert price["note"] == PRICE_UNKNOWN
        else:
            assert isinstance(price["amount"], int)
            raw_items = directory_store.cities[slug].get("tariffs", {}).get("items", [])
            first = next(i for i in raw_items if isinstance(i, dict) and i.get("price") is not None)
            expected_is_from = (
                True if first.get("price_is_from") is None else bool(first["price_is_from"])
            )
            assert price["is_from"] is expected_is_from
            assert price["note"] == PRICE_DISCLAIMER


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


def test_parse_accepts_include_done(client: TestClient) -> None:
    """POST /api/parse принимает include_done и передаёт его в задачу."""
    accepted = ParseJob(job_id="jobinclude", status=JobStatus.PENDING, include_done=True)
    with patch.object(jobs_service, "start_job", return_value=accepted) as start_job:
        response = client.post("/api/parse", json={"include_done": True})
    assert response.status_code == 202, response.text
    start_job.assert_called_once()
    assert start_job.call_args.kwargs["include_done"] is True
    assert response.json()["job_id"] == "jobinclude"


def test_parse_only_does_not_shrink_cities(client: TestClient, tmp_path, monkeypatch) -> None:
    """POST /api/parse с only не уменьшает число городов в /api/health."""
    import shutil
    import time
    from pathlib import Path

    from app.core.config import settings
    from app.services.directory_service import directory_store

    data_src = Path("app/services/directory_service/data")
    directory_dir = tmp_path / "directory"
    shutil.copytree(data_src, directory_dir)
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    index_path = tmp_path / "index.json"

    monkeypatch.setattr(settings, "directory_data_dir", directory_dir)
    monkeypatch.setattr(settings, "raw_dir", raw_dir)
    monkeypatch.setattr(settings, "out_dir", out_dir)
    monkeypatch.setattr(settings, "index_path", index_path)
    monkeypatch.setattr(settings, "parse_pause", 0.0)

    directory_store.load(data_dir=directory_dir)
    before = client.get("/api/health").json()["cities_count"]
    assert before > 1

    fixture_text = Path("tests/fixtures/city_sample.txt").read_text(encoding="utf-8")
    html = (
        "<html><body>"
        + "".join(f"<p>{line}</p>" for line in fixture_text.splitlines())
        + "</body></html>"
    )

    def fake_fetch(url: str, **kwargs) -> str:
        return html

    monkeypatch.setattr("app.services.parsing_service.fetch.fetch", fake_fetch)

    response = client.post("/api/parse", json={"only": ["tara"]})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    status: dict = {}
    for _ in range(200):
        status = client.get(f"/api/parse/{job_id}").json()
        if status["status"] in (JobStatus.DONE, JobStatus.FAILED):
            break
        time.sleep(0.05)

    assert status.get("status") == JobStatus.DONE, status
    after = client.get("/api/health").json()["cities_count"]
    assert after == before

    directory_store.load()


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


def test_nearest_branches_ok(client: TestClient) -> None:
    """GET /api/branches/nearest отдаёт 200 и distance_km по возрастанию."""
    from app.services.directory_service.store import directory_store

    directory_store.load()
    city = next(iter(directory_store.cities.values()))
    offices = [
        b
        for b in city["branches"]["items"]
        if not b.get("is_autodrome") and "открыт" not in (b.get("hours") or "").lower()
    ]
    assert len(offices) >= 2
    offices[0]["lat"], offices[0]["lon"] = 55.7500, 37.6200
    offices[1]["lat"], offices[1]["lon"] = 55.7600, 37.6300

    response = client.get(
        "/api/branches/nearest",
        params={"lat": 55.7500, "lon": 37.6200, "limit": 5, "radius_km": 50},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) >= 2
    distances = [item["distance_km"] for item in data]
    assert distances == sorted(distances)
    for item in data:
        assert {"slug", "city", "address", "landmark", "distance_km"} <= set(item)


def test_nearest_branches_invalid_coords(client: TestClient) -> None:
    """Невалидные lat/lon дают 422."""
    bad_lat = client.get("/api/branches/nearest", params={"lat": 91, "lon": 30})
    assert bad_lat.status_code == 422
    bad_lon = client.get("/api/branches/nearest", params={"lat": 55, "lon": 181})
    assert bad_lon.status_code == 422


def test_nearest_does_not_collide_with_branch_slug(client: TestClient) -> None:
    """/branches/nearest не перехватывается маршрутом /branches/{branch_slug}."""
    response = client.get("/api/branches/nearest", params={"lat": 0, "lon": 0})
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_geocode_found(client: TestClient, monkeypatch) -> None:
    """GET /api/geocode с заглушкой геокодера возвращает found=true и координаты."""

    class FakeGeocoder:
        async def geocode(self, text: str) -> tuple[float, float] | None:
            return 59.85, 30.35

    monkeypatch.setattr(
        "app.services.directory_service.api.geocoder",
        FakeGeocoder(),
    )
    response = client.get("/api/geocode", params={"text": "Купчино"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["found"] is True
    assert data["lat"] == 59.85
    assert data["lon"] == 30.35
    assert data["text"] == "Купчино"


def test_geocode_not_found(client: TestClient, monkeypatch) -> None:
    """Нераспознанное место даёт found=false и статус 200."""

    class FakeGeocoder:
        async def geocode(self, text: str) -> tuple[float, float] | None:
            return None

    monkeypatch.setattr(
        "app.services.directory_service.api.geocoder",
        FakeGeocoder(),
    )
    response = client.get("/api/geocode", params={"text": "нигде"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["found"] is False
    assert data["lat"] is None
    assert data["lon"] is None


def test_geocode_text_appends_city(monkeypatch) -> None:
    """geocode_text с city_slug передаёт в геокодер «место, Город»."""
    captured: list[str] = []

    class FakeGeocoder:
        async def geocode(self, text: str) -> tuple[float, float] | None:
            captured.append(text)
            return 59.85, 30.35

    monkeypatch.setattr(
        "app.services.directory_service.api.geocoder",
        FakeGeocoder(),
    )
    from app.services.directory_service import api as directory_api

    result = asyncio.run(directory_api.geocode_text("Купчино", city_slug="sankt-peterburg"))
    assert captured == ["Купчино, Санкт-Петербург"]
    assert result.text == "Купчино"
    assert result.found is True


def test_geocode_text_without_city_or_unknown_slug(monkeypatch) -> None:
    """Без city_slug и с несуществующим слагом текст уходит как есть."""
    captured: list[str] = []

    class FakeGeocoder:
        async def geocode(self, text: str) -> tuple[float, float] | None:
            captured.append(text)
            return None

    monkeypatch.setattr(
        "app.services.directory_service.api.geocoder",
        FakeGeocoder(),
    )
    from app.services.directory_service import api as directory_api

    asyncio.run(directory_api.geocode_text("Купчино"))
    asyncio.run(directory_api.geocode_text("Купчино", city_slug="нет-такого"))
    assert captured == ["Купчино", "Купчино"]
