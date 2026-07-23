"""Сборка индекса городов и филиалов.

Читает JSON из каталога собранных данных и пишет файл индекса.
Пути передаются параметрами (по умолчанию — из настроек).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings


def run(
    *,
    out_dir: Path | None = None,
    index_path: Path | None = None,
) -> int:
    """Собирает индекс и печатает готовые enum.

    Args:
        out_dir: каталог полных JSON городов.
        index_path: путь к файлу индекса.

    Returns:
        Код возврата процесса.
    """
    src = out_dir if out_dir is not None else settings.out_dir
    index_file = index_path if index_path is not None else settings.index_path

    cities = []
    for path in sorted(p for p in src.glob("*.json") if p.stem != "_index"):
        city = json.loads(path.read_text(encoding="utf-8"))
        cities.append(
            {
                "slug": city["meta"]["city_slug"],
                "name": city["meta"]["city"],
                "branches": [
                    {"id": b["id"], "address": b["address"], "is_autodrome": b["is_autodrome"]}
                    for b in city["branches"]["items"]
                ],
            }
        )

    cities.sort(key=lambda c: c["name"])
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(
        json.dumps({"cities": cities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total = sum(len(c["branches"]) for c in cities)
    print(f"Городов {len(cities)}, филиалов {total} → {index_file}")
    print("\nenum city_slug:")
    print(json.dumps([c["slug"] for c in cities], ensure_ascii=False))
    return 0
