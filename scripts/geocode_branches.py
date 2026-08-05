"""Проставляет координаты филиалам через Nominatim.

Обходит JSON городов, для каждого филиала с пустыми ``lat``/``lon`` строит
запрос «адрес, город» и пишет найденную точку обратно в файл. Уже заполненные
координаты пропускает — скрипт можно перезапускать.

Перед запросом адрес нормализуется: этаж и офис срезаются, опечатки вроде
«ул,» чинятся. В справочнике полный адрес не меняется.

Частоту запросов ограничивает ``geopy.extra.rate_limiter.RateLimiter``.

Запуск:
    uv run python scripts/geocode_branches.py
    uv run python scripts/geocode_branches.py --city sankt-peterburg
    uv run python scripts/geocode_branches.py --dry-run
    uv run python scripts/geocode_branches.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.directory_service.address import normalize_for_geocoder
from app.services.directory_service.geocoders.nominatim import NominatimGeocoder
from geopy.extra.rate_limiter import RateLimiter

#: Сколько первых подряд промахов считать признаком отказа провайдера.
EARLY_MISS_ABORT = 3


class ProviderLikelyRejected(Exception):
    """Первые запросы к геокодеру все вернули None — дальше гонять бессмысленно."""


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки.

    Возвращает:
        Разобранные аргументы ``--city``, ``--dry-run``, ``--force``.
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Повторно геокодировать филиалы с уже заполненными координатами",
    )
    parser.add_argument(
        "--only-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Обрабатывать только филиалы без координат (по умолчанию включено)",
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


def should_process(branch: dict[str, Any], *, force: bool, only_missing: bool) -> bool:
    """Решает, нужно ли геокодировать филиал в этом прогоне.

    Аргументы:
        branch: запись филиала.
        force: перезаписывать уже заполненные координаты.
        only_missing: обрабатывать только пустые координаты.

    Возвращает:
        True, если филиал участвует в прогоне.
    """
    if force:
        return True
    if only_missing:
        return needs_coords(branch)
    return True


def process_city(
    path: Path,
    geocode: Any,
    *,
    dry_run: bool,
    force: bool,
    only_missing: bool,
) -> tuple[int, int, int]:
    """Обрабатывает один файл города.

    Аргументы:
        path: путь к JSON города.
        geocode: функция геокодинга (уже с RateLimiter и ранним стопом).
        dry_run: если True — не писать файл.
        force: перезаписывать уже заполненные координаты.
        only_missing: обрабатывать только филиалы без координат.

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
        if not should_process(branch, force=force, only_missing=only_missing):
            continue
        processed += 1
        address = branch.get("address") or ""
        cleaned = normalize_for_geocoder(address)
        query = f"{cleaned}, {city_title}"
        point = geocode(query)
        if point is None:
            missed += 1
            print(f"  miss  {city_title}: {address}")
            if cleaned != address:
                print(f"         запрос: {cleaned}")
            continue
        lat, lon = point
        print(f"  ok    {city_title}: {address} -> {lat:.6f}, {lon:.6f}")
        if cleaned != address:
            print(f"         запрос: {cleaned}")
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
    if not settings.geocoder_contact.strip():
        print(
            "Не задан GEOCODER_CONTACT. Nominatim требует реальный e-mail или "
            "адрес сайта в переменной окружения — без него запросы отклоняются."
        )
        sys.exit(1)

    args = parse_args()
    only_missing = False if args.force else args.only_missing
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

    first_hits: list[bool] = []

    def geocode_with_early_abort(query: str) -> tuple[float, float] | None:
        """Вызывает геокодер и прерывает прогон после трёх первых промахов."""
        point = geocode(query)
        if len(first_hits) < EARLY_MISS_ABORT:
            first_hits.append(point is not None)
            if len(first_hits) == EARLY_MISS_ABORT and not any(first_hits):
                raise ProviderLikelyRejected
        return point

    total_processed = 0
    total_filled = 0
    total_missed = 0
    try:
        for path in files:
            print(f"{path.stem}")
            processed, filled, missed = process_city(
                path,
                geocode_with_early_abort,
                dry_run=args.dry_run,
                force=args.force,
                only_missing=only_missing,
            )
            total_processed += processed
            total_filled += filled
            total_missed += missed
    except ProviderLikelyRejected:
        print(
            "Провайдер, судя по всему, отклоняет запросы: первые "
            f"{EARLY_MISS_ABORT} обращения вернули пустой ответ. "
            "Проверьте GEOCODER_CONTACT и политику Nominatim. Прогон прерван."
        )
        sys.exit(1)

    print(
        f"Итого: обработано {total_processed} / "
        f"проставлено {total_filled} / не найдено {total_missed}"
    )


if __name__ == "__main__":
    main()
