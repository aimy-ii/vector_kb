"""Чёрный ящик API: HTTP к поднятому сервису."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from utils.api_client import APIClient

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def _load_dotenv(path: Path) -> None:
    """Читает KEY=VALUE из файла в окружение, не перезаписывая уже заданные."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def pytest_configure() -> None:
    """Подгружает переменные окружения api_tests."""
    if ENV_PATH.exists():
        _load_dotenv(ENV_PATH)
    else:
        _load_dotenv(ENV_EXAMPLE)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Базовый URL сервиса."""
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8317")


@pytest.fixture(scope="session")
def public_client(base_url: str) -> APIClient:
    """HTTP-клиент без аутентификации."""
    return APIClient(base_url=base_url)
