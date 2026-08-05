"""Проставляет координаты филиалам через Nominatim.

Обходит JSON городов, для каждого филиала с пустыми ``lat``/``lon`` строит
запрос «адрес, город» и пишет найденную точку обратно в файл. Уже заполненные
координаты пропускает — скрипт можно перезапускать.

Частоту запросов ограничивает ``geopy.extra.rate_limiter.RateLimiter``.

Запуск:
    uv run python scripts/geocode_branches.py
    uv run python scripts/geocode_branches.py --city sankt-peterburg
    uv run python scripts/geocode_branches.py --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.directory_service.geocoders.nominatim import NominatimGeocoder
from geopy.extra.rate_limiter import RateLimiter


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки.

    Возвращает:
        Разобранные аргументы ``--city`` и ``--dry-run``.
    """
    parser = argparse.ArgumentParser(description="Простановка координат филиалам")
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Слаг города: обработать только его файл",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Не записывать изменения на диск",
    )
    return parser.parse_args()


def city_files(data_dir: Path, city_slug: str | None) -> list[Path]:
    """Подбирает файлы городов для обработки.

    Аргументы:
        data_dir: каталог со справочником.
        city_slug: слаг одного города или None для всех.

    Возвращает:
        Отсортированный список путей к JSON.
    """
    if city_slug is None:
        return sorted(data_dir.glob("*.json"))
    path = data_dir / f"{city_slug}.json"
    return [path] if path.is_file() else []


def needs_coords(branch: dict[str, Any]) -> bool:
    """Проверяет, что у филиала ещё нет координат.

    Аргументы:
        branch: запись филиала из JSON.

    Возвращает:
        True, если lat или lon пусты и точку нужно искать.
    """
    return branch.get("lat") is None or branch.get("lon") is None


def process_city(
    path: Path,
    geocode: Any,
    *,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Обрабатывает один файл города.

    Аргументы:
        path: путь к JSON города.
        geocode: функция геокодинга (уже с RateLimiter).
        dry_run: если True — не писать файл.

    Возвращает:
        Кортеж (обработано, проставлено, не найдено).
    """
    city = json.loads(path.read_text(encoding="utf-8"))
    city_title = city.get("meta", {}).get("city", path.stem)
    processed = 0
    filled = 0
    missed = 0
    changed = False

    for branch in city.get("branches", {}).get("items", []):
        if not needs_coords(branch):
            continue
        processed += 1
        address = branch.get("address") or ""
        query = f"{address}, {city_title}"
        point = geocode(query)
        if point is None:
            missed += 1
            print(f"  miss  {city_title}: {address}")
            continue
        lat, lon = point
        print(f"  ok    {city_title}: {address} -> {lat:.6f}, {lon:.6f}")
        if not dry_run:
            branch["lat"] = lat
            branch["lon"] = lon
            changed = True
        filled += 1

    if changed and not dry_run:
        path.write_text(
            json.dumps(city, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return processed, filled, missed


def main() -> None:
    """Проходит по городам и печатает сводку простановки координат."""
    args = parse_args()
    data_dir = settings.directory_data_dir
    files = city_files(data_dir, args.city)
    if not files:
        target = args.city or str(data_dir)
        print(f"Файлов городов не найдено: {target}")
        return

    geocoder = NominatimGeocoder()
    geocode = RateLimiter(
        geocoder.geocode_sync,
        min_delay_seconds=settings.geocoder_pause,
    )

    total_processed = 0
    total_filled = 0
    total_missed = 0
    for path in files:
        print(f"{path.stem}")
        processed, filled, missed = process_city(path, geocode, dry_run=args.dry_run)
        total_processed += processed
        total_filled += filled
        total_missed += missed

    print(
        f"Итого: обработано {total_processed} / "
        f"проставлено {total_filled} / не найдено {total_missed}"
    )


if __name__ == "__main__":
    main()
