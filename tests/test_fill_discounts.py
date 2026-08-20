"""Офлайн-тесты скрипта заполнения скидок в файлах городов.

Работают на временном каталоге с копиями файлов — настоящие данные
в `app/services/directory_service/data` не меняются.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.fill_discounts import DISCOUNTS, fill_discounts, process_city

#: Минимальный каркас города для изоляции тестов.
_CITY_TEMPLATE: dict[str, Any] = {
    "city": {"slug": "demo-city", "name": "Демо"},
    "tariffs": {"_source": "https://example.test", "items": []},
}


def _write_city(path: Path, city: dict[str, Any]) -> Path:
    """Пишет JSON города во временный файл.

    Args:
        path: путь к файлу.
        city: содержимое города.

    Returns:
        Тот же путь.
    """
    path.write_text(
        json.dumps(city, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _read_city(path: Path) -> dict[str, Any]:
    """Читает JSON города.

    Args:
        path: путь к файлу.

    Returns:
        Разобранный словарь.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_discounts_gets_all_phrases(tmp_path: Path) -> None:
    """Город без ключа discounts получает все шесть фраз в порядке DISCOUNTS."""
    path = _write_city(tmp_path / "city.json", json.loads(json.dumps(_CITY_TEMPLATE)))
    assert process_city(path) is True
    city = _read_city(path)
    assert city["discounts"] == list(DISCOUNTS)


def test_empty_discounts_list_filled(tmp_path: Path) -> None:
    """Город с пустым списком discounts заполняется."""
    city = json.loads(json.dumps(_CITY_TEMPLATE))
    city["discounts"] = []
    assert fill_discounts(city) is True
    assert city["discounts"] == list(DISCOUNTS)

    empty_city = json.loads(json.dumps(_CITY_TEMPLATE | {"discounts": []}))
    path = _write_city(tmp_path / "city.json", empty_city)
    assert process_city(path) is True
    assert _read_city(path)["discounts"] == list(DISCOUNTS)


def test_nonempty_discounts_untouched(tmp_path: Path) -> None:
    """Город с непустым списком не меняется: False и файл байт в байт прежний."""
    original = ["своя акция"]
    city = json.loads(json.dumps(_CITY_TEMPLATE))
    city["discounts"] = list(original)
    path = _write_city(tmp_path / "city.json", city)
    before = path.read_text(encoding="utf-8")

    assert fill_discounts(city) is False
    assert process_city(path) is False
    assert path.read_text(encoding="utf-8") == before
    assert _read_city(path)["discounts"] == original


def test_second_run_idempotent(tmp_path: Path) -> None:
    """Повторный запуск process_city возвращает False и не меняет файл побайтово."""
    path = _write_city(tmp_path / "city.json", json.loads(json.dumps(_CITY_TEMPLATE)))
    assert process_city(path) is True
    text_after_first = path.read_text(encoding="utf-8")

    assert process_city(path) is False
    assert path.read_text(encoding="utf-8") == text_after_first


def test_discounts_phrases_have_no_price_leaks() -> None:
    """Ни одна фраза из DISCOUNTS не содержит «цена» и символ «₽»."""
    for phrase in DISCOUNTS:
        assert "цена" not in phrase
        assert "₽" not in phrase
