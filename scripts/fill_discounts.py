"""Заполняет раздел скидок в файлах городов справочника.

Тексты взяты с официального сайта и агрегатора; формулировки не менять.
Скрипт идемпотентен: непустой список ``discounts`` не перезаписывается.

Запуск:
    uv run python scripts/fill_discounts.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Каталог с файлами городов.
DATA_DIR = Path("app/services/directory_service/data")

#: Готовые фразы скидок и акций (порядок фиксирован).
DISCOUNTS: tuple[str, ...] = (
    "студентам и школьникам скидка до 1000 рублей",
    "молодым мамам скидка до 1000 рублей",
    "именинникам скидка 1000 рублей на любой пакет обучения",
    "при заключении договора в день обращения скидка 1000 рублей",
    "приведи друга и получи скидку — можно использовать самому или разделить на двоих",
    (
        "скидки обновляются каждый месяц, максимальная выгода до 30 процентов "
        "на пакет, размер прописывается в договоре"
    ),
)


def fill_discounts(city: dict[str, Any]) -> bool:
    """Заполняет раздел скидок, если ключа нет или список пуст.

    Args:
        city: разобранный JSON города, меняется на месте.

    Returns:
        True, если раздел был изменён; False, если уже был непустой список.
    """
    current = city.get("discounts")
    if isinstance(current, list) and current:
        return False
    city["discounts"] = list(DISCOUNTS)
    return True


def process_city(path: Path) -> bool:
    """Обрабатывает один файл города: читает, заполняет скидки, пишет при изменении.

    Args:
        path: путь к JSON-файлу города.

    Returns:
        True, если файл был изменён.
    """
    city = json.loads(path.read_text(encoding="utf-8"))
    changed = fill_discounts(city)
    if changed:
        path.write_text(
            json.dumps(city, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> None:
    """Проходит по всем городам и печатает сводку заполнения скидок."""
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print(f"Файлов городов не найдено в {DATA_DIR}")
        return

    filled = 0
    for path in files:
        filled += int(process_city(path))

    print(f"Городов обработано: {len(files)}")
    print(f"  раздел скидок заполнен: {filled}")


if __name__ == "__main__":
    main()
