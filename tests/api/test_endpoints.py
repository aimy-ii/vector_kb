"""Тесты HTTP-эндпоинтов через TestClient."""

from __future__ import annotations

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
            assert price["is_from"] is True
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
