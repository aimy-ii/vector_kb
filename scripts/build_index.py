"""Сборка индекса городов и филиалов.

Запуск из корня проекта:

    uv run python scripts/build_index.py

Читает `data/out/*.json` и пишет `data/index.json` — компактный список городов с их
слагами и филиалами. Из него берутся значения enum для инструментов модели.
Пути к данным считаются от корня проекта, а не от каталога скрипта.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "out"
INDEX = ROOT / "data" / "index.json"


def main() -> int:
    """Собирает индекс и печатает готовые enum.

    Возвращает:
        Код возврата процесса.
    """
    cities = []
    for path in sorted(p for p in OUT_DIR.glob("*.json") if p.stem != "_index"):
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
    INDEX.write_text(
        json.dumps({"cities": cities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total = sum(len(c["branches"]) for c in cities)
    print(f"Городов {len(cities)}, филиалов {total} → {INDEX}")
    print("\nenum city_slug:")
    print(json.dumps([c["slug"] for c in cities], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
