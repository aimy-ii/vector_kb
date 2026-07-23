"""Сборка урезанных JSON городов для справочника.

Читает полные файлы из каталога собранных JSON, оставляет только поля,
нужные агенту, и пишет результат в каталог данных справочника.
Пути передаются параметрами (по умолчанию — из настроек).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings

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


def run(
    *,
    src_dir: Path | None = None,
    dst_dir: Path | None = None,
) -> int:
    """Собирает урезанные файлы и печатает статистику объёма.

    Args:
        src_dir: каталог полных JSON городов.
        dst_dir: каталог урезанных данных справочника.

    Returns:
        Код возврата: 0 — успех, 1 — нет исходных файлов.
    """
    src = src_dir if src_dir is not None else settings.out_dir
    dst = dst_dir if dst_dir is not None else settings.directory_data_dir
    files = sorted(p for p in src.glob("*.json") if not p.stem.startswith("_"))
    if not files:
        print(f"Нет файлов в {src}")
        return 1

    dst.mkdir(parents=True, exist_ok=True)
    for stale in dst.glob("*.json"):
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
        (dst / path.name).write_bytes(encoded)

    saved = before - after
    percent = (100.0 * saved / before) if before else 0.0
    print(f"Файлов: {len(files)}")
    print(f"Было: {before} байт → стало: {after} байт (−{saved} байт, −{percent:.1f}%)")
    print(f"Каталог: {dst}")
    return 0
