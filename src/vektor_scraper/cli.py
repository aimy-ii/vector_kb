"""Командный интерфейс: обойти города, разобрать страницы, сложить JSON.

Запуск одной командой:
    uv run vektor-scrape
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from vektor_scraper import cities as cities_mod
from vektor_scraper.fetch import collect_links, fetch_to_disk
from vektor_scraper.parse import build


def _args(argv: list[str] | None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="vektor-scrape",
        description="Сбор справочника автошколы «Вектор» по городам в JSON",
    )
    parser.add_argument("--out", default="data", help="каталог для результатов (по умолчанию data)")
    parser.add_argument("--only", nargs="*", help="слаги конкретных городов")
    parser.add_argument("--include-done", action="store_true", help="включая уже собранные вручную")
    parser.add_argument("--external", action="store_true", help="включая города на чужих доменах")
    parser.add_argument("--force", action="store_true", help="перекачать, игнорируя кэш")
    parser.add_argument("--pause", type=float, default=1.5, help="пауза между городами, секунд")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Аргументы:
        argv: аргументы командной строки; None — взять из sys.argv.

    Возвращает:
        Код возврата процесса: 0 — все города разобраны, 1 — были ошибки.
    """
    args = _args(argv)
    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"
    json_dir = out_dir / "out"
    json_dir.mkdir(parents=True, exist_ok=True)

    targets = cities_mod.select(
        include_done=args.include_done,
        include_external=args.external,
        only=args.only,
    )
    if not targets:
        print("Нечего собирать: список городов после фильтров пуст.")
        return 0

    today = date.today().isoformat()
    failures: list[str] = []
    index: list[dict[str, object]] = []

    print(f"Городов к обходу: {len(targets)}\n")
    for number, city in enumerate(targets, start=1):
        prefix = f"[{number}/{len(targets)}] {city.name}"
        try:
            html, text = fetch_to_disk(city.slug, city.url, raw_dir, force=args.force)
            document = build(city.slug, city.name, city.url, text, collect_links(html), today)
            path = json_dir / f"{city.slug}.json"
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            branches = len(document["branches"]["items"])
            promos = len(document["promos"]["items"])
            prices = len(document["tariffs"]["prices_found"])
            conflicts = len(document["conflicts"])
            print(
                f"{prefix}: филиалов {branches}, акций {promos}, "
                f"сумм {prices}, расхождений {conflicts} → {path}"
            )
            index.append(
                {
                    "slug": city.slug,
                    "city": city.name,
                    "url": city.url,
                    "branches": branches,
                    "promos": promos,
                    "prices_found": prices,
                    "conflicts": conflicts,
                    "review": document["_review"],
                }
            )
        except Exception as exc:  # noqa: BLE001 — падение одного города не должно рвать обход
            print(f"{prefix}: ОШИБКА — {exc}", file=sys.stderr)
            failures.append(city.slug)
        if number < len(targets):
            time.sleep(args.pause)

    (json_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nГотово: {len(index)} городов в {json_dir}, сырые страницы в {raw_dir}")
    if failures:
        print(f"Не собрались: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
