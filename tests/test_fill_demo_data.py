"""Офлайн-тесты скрипта демонстрационных данных справочника.

Работают на временном каталоге с копиями файлов городов — настоящие данные
в `app/services/directory_service/data` не меняются.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from scripts.fill_demo_data import (
    DOWN_PAYMENT,
    PRICE_BASE,
    TERM_MONTHS,
    fill_category_b,
    fill_installment,
    fill_tariffs,
    process_city,
)

#: Минимальный каркас города для изоляции тестов.
_CITY_TEMPLATE: dict[str, Any] = {
    "city": {"slug": "demo-city", "name": "Демо"},
    "tariffs": {"_source": "https://example.test", "items": []},
    "installment": {
        "_source": "https://example.test",
        "term_months": None,
        "down_payment": None,
    },
    "categories": {
        "_source": "https://example.test",
        "items": [
            {
                "id": "cat_b",
                "code": "B",
                "name": "Категория В",
                "price": None,
                "price_note": "нет цены",
            }
        ],
    },
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


def _copy_template(tmp_path: Path, name: str = "city.json") -> Path:
    """Кладёт копию шаблона города во временный каталог.

    Args:
        tmp_path: временный каталог pytest.
        name: имя файла.

    Returns:
        Путь к созданному файлу.
    """
    return _write_city(tmp_path / name, json.loads(json.dumps(_CITY_TEMPLATE)))


def test_empty_tariffs_get_two_demo_items(tmp_path: Path) -> None:
    """Город с пустым разделом тарифов получает два тарифа, первый — 39 900."""
    path = _copy_template(tmp_path)
    result = process_city(path)

    assert result["tariffs"] is True
    city = _read_city(path)
    items = city["tariffs"]["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Базовый"
    assert items[0]["price"] == PRICE_BASE
    assert items[1]["name"] == "Расширенный"


def test_nonempty_tariffs_untouched(tmp_path: Path) -> None:
    """Город с непустым разделом тарифов не меняется."""
    city = json.loads(json.dumps(_CITY_TEMPLATE))
    original = {
        "id": "existing",
        "name": "Уже есть",
        "price": 10000,
        "price_is_from": True,
        "includes": [],
    }
    city["tariffs"]["items"] = [original]
    # Остальные разделы уже заполнены — process_city не должен трогать файл.
    city["installment"]["term_months"] = 12
    city["installment"]["down_payment"] = 1000
    city["categories"]["items"][0]["price"] = 11111
    path = _write_city(tmp_path / "city.json", city)
    before = path.read_text(encoding="utf-8")

    assert fill_tariffs(city) is False
    result = process_city(path)

    assert result == {"tariffs": False, "installment": False, "category_b": False}
    assert path.read_text(encoding="utf-8") == before
    assert _read_city(path)["tariffs"]["items"] == [original]


def test_installment_fills_only_empty(tmp_path: Path) -> None:
    """Пустые срок и взнос заполняются; непустые не трогаются."""
    empty = json.loads(json.dumps(_CITY_TEMPLATE))
    assert fill_installment(empty) is True
    assert empty["installment"]["term_months"] == TERM_MONTHS
    assert empty["installment"]["down_payment"] == DOWN_PAYMENT

    partial = json.loads(json.dumps(_CITY_TEMPLATE))
    partial["installment"]["term_months"] = 12
    partial["installment"]["down_payment"] = None
    assert fill_installment(partial) is True
    assert partial["installment"]["term_months"] == 12
    assert partial["installment"]["down_payment"] == DOWN_PAYMENT

    full = json.loads(json.dumps(_CITY_TEMPLATE))
    full["installment"]["term_months"] = 3
    full["installment"]["down_payment"] = 1000
    assert fill_installment(full) is False
    assert full["installment"]["term_months"] == 3
    assert full["installment"]["down_payment"] == 1000

    path = _write_city(tmp_path / "city.json", json.loads(json.dumps(_CITY_TEMPLATE)))
    process_city(path)
    saved = _read_city(path)["installment"]
    assert saved["term_months"] == TERM_MONTHS
    assert saved["down_payment"] == DOWN_PAYMENT


def test_category_b_price_fill_and_preserve(tmp_path: Path) -> None:
    """Цена категории B проставляется, если её нет, и не меняется, если есть."""
    empty = json.loads(json.dumps(_CITY_TEMPLATE))
    assert fill_category_b(empty) is True
    assert empty["categories"]["items"][0]["price"] == PRICE_BASE

    priced = json.loads(json.dumps(_CITY_TEMPLATE))
    priced["categories"]["items"][0]["price"] = 11111
    assert fill_category_b(priced) is False
    assert priced["categories"]["items"][0]["price"] == 11111

    path = _write_city(tmp_path / "city.json", json.loads(json.dumps(_CITY_TEMPLATE)))
    process_city(path)
    assert _read_city(path)["categories"]["items"][0]["price"] == PRICE_BASE


def test_second_run_idempotent(tmp_path: Path) -> None:
    """Повторный запуск не меняет файлы и не создаёт дублей."""
    path = _copy_template(tmp_path)
    first = process_city(path)
    assert any(first.values())
    text_after_first = path.read_text(encoding="utf-8")
    city_after_first = _read_city(path)

    second = process_city(path)
    assert second == {"tariffs": False, "installment": False, "category_b": False}
    assert path.read_text(encoding="utf-8") == text_after_first
    assert len(_read_city(path)["tariffs"]["items"]) == len(city_after_first["tariffs"]["items"])


def test_demo_flag_on_all_additions(tmp_path: Path) -> None:
    """У всех добавленных записей стоит признак демонстрационных данных."""
    path = _copy_template(tmp_path)
    process_city(path)
    city = _read_city(path)

    for item in city["tariffs"]["items"]:
        assert item.get("_demo") is True
    assert city["installment"].get("_demo") is True
    assert city["categories"]["items"][0].get("_demo") is True


def test_process_city_on_copied_real_empty_city(tmp_path: Path) -> None:
    """Копия реального города с пустыми тарифами заполняется офлайн."""
    real = Path("app/services/directory_service/data/ekaterinburg.json")
    if not real.is_file():
        pytest.skip("файл Екатеринбурга недоступен")
    path = tmp_path / "ekaterinburg.json"
    shutil.copy2(real, path)
    before_items = _read_city(path)["tariffs"]["items"]
    if before_items:
        assert process_city(path)["tariffs"] is False
        return

    assert process_city(path)["tariffs"] is True
    city = _read_city(path)
    assert city["tariffs"]["items"][0]["price"] == PRICE_BASE
    assert city["tariffs"]["items"][0]["_demo"] is True
