"""Синхронный HTTP-клиент для чёрного ящика API."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "email",
    "full_name",
    "password",
    "token",
    "username",
}


def _redact(value: Any) -> Any:
    """Маскирует чувствительные поля перед логированием."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return "***@***"
    return value


class APIClient:
    """Небольшой синхронный клиент на httpx."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def get(self, path: str, **kwargs) -> httpx.Response:
        """GET-запрос."""
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        """POST-запрос."""
        return self._request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        """DELETE-запрос."""
        return self._request("DELETE", path, **kwargs)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Выполняет запрос и пишет в лог без секретов."""
        logger.info("%s %s payload=%s", method, path, _redact(kwargs.get("json")))
        response = self._client.request(method, path, **kwargs)
        logger.info("← %s %s", response.status_code, _redact(self._safe_json(response)))
        return response

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        """Пытается разобрать JSON; иначе возвращает текст."""
        try:
            return response.json()
        except Exception:  # noqa: BLE001
            return response.text
