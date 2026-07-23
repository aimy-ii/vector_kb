"""Сборка урезанных JSON городов для пакета `vektor_directory`.

Запуск из корня проекта:

    uv run python scripts/build_package_data.py

Читает полные файлы из `data/out`, оставляет только поля, нужные агенту,
и пишет результат в `vektor_directory/data/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "out"
DST_DIR = ROOT / "vektor_directory" / "data"

KEEP_KEYS = (
    "meta",
    "branches",
    "categories",
    "fleet",
    "theory_formats",
    "documents",
    "faq",
    "installment",
    "contacts",
)


def _trim_faq(section: Any) -> dict[str, Any]:
    """Оставляет в FAQ только пары с непустым ответом."""
    if not isinstance(section, dict):
        return {"items": []}
    items = [
        item for item in section.get("items", []) if isinstance(item, dict) and item.get("answer")
    ]
    result = dict(section)
    result["items"] = items
    return result


def trim_city(city: dict[str, Any]) -> dict[str, Any]:
    """Урезает полный файл города до полей пакета.

    Аргументы:
        city: полный разобранный JSON города.

    Возвращает:
        Словарь только с ключами, нужными агенту.
    """
    trimmed: dict[str, Any] = {}
    for key in KEEP_KEYS:
        if key not in city:
            continue
        if key == "faq":
            trimmed[key] = _trim_faq(city[key])
        else:
            trimmed[key] = city[key]
    return trimmed


def main() -> int:
    """Собирает урезанные файлы и печатает статистику объёма.

    Возвращает:
        Код возврата процесса.
    """
    files = sorted(p for p in SRC_DIR.glob("*.json") if not p.stem.startswith("_"))
    if not files:
        print(f"Нет файлов в {SRC_DIR}")
        return 1

    DST_DIR.mkdir(parents=True, exist_ok=True)
    for stale in DST_DIR.glob("*.json"):
        stale.unlink()

    before = 0
    after = 0
    for path in files:
        raw = path.read_bytes()
        before += len(raw)
        city = json.loads(raw.decode("utf-8"))
        trimmed = trim_city(city)
        out = json.dumps(trimmed, ensure_ascii=False, indent=2) + "\n"
        encoded = out.encode("utf-8")
        after += len(encoded)
        (DST_DIR / path.name).write_bytes(encoded)

    saved = before - after
    percent = (100.0 * saved / before) if before else 0.0
    print(f"Файлов: {len(files)}")
    print(f"Было: {before} байт → стало: {after} байт (−{saved} байт, −{percent:.1f}%)")
    print(f"Каталог: {DST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
