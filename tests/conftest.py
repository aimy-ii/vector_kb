"""Общие фикстуры unit-тестов."""

from __future__ import annotations

import os

# Контакт нужен до импорта приложения: синглтон геокодера создаётся при загрузке.
os.environ.setdefault("GEOCODER_CONTACT", "geocoder-tests@localhost")

import pytest
from app.main import app
from app.services.directory_service import directory_store
from app.services.parsing_service import jobs as jobs_service
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _ensure_directory_loaded() -> None:
    """Гарантирует загруженный справочник и чистый реестр задач."""
    if not directory_store.cities:
        directory_store.load()
    jobs_service._jobs.clear()
    jobs_service._active_job_id = None


@pytest.fixture
def client() -> TestClient:
    """HTTP-клиент FastAPI без реального сетевого сервера."""
    with TestClient(app) as test_client:
        yield test_client
