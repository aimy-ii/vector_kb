"""Заполняет демонстрационные данные в файлах городов справочника.

Данные вымышленные, нужны для показа заказчику: какую цену поставим — такую
бот и озвучит. Каждая добавленная запись помечена ``"_demo": true``.

Скрипт идемпотентен: повторный запуск ничего не портит и не плодит дублей.
Непустые значения не перезаписываются — трогаются только ``null`` и пустые
списки.

Запуск:
    uv run python scripts/fill_demo_data.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Каталог с файлами городов.
DATA_DIR = Path("app/services/directory_service/data")

#: Цена базового тарифа, рублей.
PRICE_BASE = 39900

#: Цена расширенного тарифа, рублей.
PRICE_EXTENDED = 45900

#: Первоначальный взнос по рассрочке, рублей.
DOWN_PAYMENT = 5000

#: Срок рассрочки, месяцев.
TERM_MONTHS = 6


def demo_tariffs() -> list[dict[str, Any]]:
    """Два демонстрационных тарифа: базовый и расширенный.

    Порядок важен: витринную цену API берёт из первого тарифа с непустой
    суммой, поэтому базовый идёт первым.

    Returns:
        Список из двух записей тарифов.
    """
    return [
        {
            "id": "tariff_base",
            "name": "Базовый",
            "price": PRICE_BASE,
            "price_is_from": False,
            "includes": [
                "полный курс теории",
                "23 часа практики с инструктором",
                "топливо и аренда автомобиля",
                "внутренний экзамен",
            ],
            "_demo": True,
        },
        {
            "id": "tariff_extended",
            "name": "Расширенный",
            "price": PRICE_EXTENDED,
            "price_is_from": False,
            "includes": [
                "полный курс теории",
                "40 часов практики с инструктором",
                "топливо и аренда автомобиля",
                "внутренний экзамен",
            ],
            "_demo": True,
        },
    ]


def fill_tariffs(city: dict[str, Any]) -> bool:
    """Заполняет раздел тарифов, если он пуст.

    Args:
        city: разобранный JSON города, меняется на месте.

    Returns:
        True, если раздел был изменён.
    """
    section = city.get("tariffs")
    if not isinstance(section, dict):
        return False
    items = section.get("items")
    if items:
        return False
    section["items"] = demo_tariffs()
    return True


def fill_installment(city: dict[str, Any]) -> bool:
    """Заполняет срок рассрочки и первый взнос, если они пусты.

    Args:
        city: разобранный JSON города, меняется на месте.

    Returns:
        True, если раздел был изменён.
    """
    section = city.get("installment")
    if not isinstance(section, dict):
        return False
    changed = False
    if section.get("term_months") is None:
        section["term_months"] = TERM_MONTHS
        changed = True
    if section.get("down_payment") is None:
        section["down_payment"] = DOWN_PAYMENT
        changed = True
    if changed:
        section["_demo"] = True
    return changed


def fill_category_b(city: dict[str, Any]) -> bool:
    """Проставляет цену категории B, если её нет.

    Args:
        city: разобранный JSON города, меняется на месте.

    Returns:
        True, если запись была изменена.
    """
    section = city.get("categories")
    if not isinstance(section, dict):
        return False
    items = section.get("items")
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict) or item.get("code") != "B":
            continue
        if item.get("price") is not None:
            return False
        item["price"] = PRICE_BASE
        item["price_note"] = "полный курс категории B"
        item["_demo"] = True
        return True
    return False


def process_city(path: Path) -> dict[str, bool]:
    """Обрабатывает один файл города.

    Args:
        path: путь к JSON-файлу города.

    Returns:
        Отметки о том, какие разделы изменились.
    """
    city = json.loads(path.read_text(encoding="utf-8"))
    result = {
        "tariffs": fill_tariffs(city),
        "installment": fill_installment(city),
        "category_b": fill_category_b(city),
    }
    if any(result.values()):
        path.write_text(
            json.dumps(city, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result


def main() -> None:
    """Проходит по всем городам и печатает сводку."""
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print(f"Файлов городов не найдено в {DATA_DIR}")
        return

    totals = {"tariffs": 0, "installment": 0, "category_b": 0}
    for path in files:
        for key, changed in process_city(path).items():
            totals[key] += int(changed)

    print(f"Городов обработано: {len(files)}")
    print(f"  тарифы заполнены:      {totals['tariffs']}")
    print(f"  рассрочка заполнена:   {totals['installment']}")
    print(f"  цена категории B:      {totals['category_b']}")


if __name__ == "__main__":
    main()
