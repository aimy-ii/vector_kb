"""Проставляет координаты филиалам через выбранный геокодер.

Обходит JSON городов, для каждого филиала с пустыми ``lat``/``lon`` строит
запрос через ``build_query`` выбранного провайдера и пишет найденную точку
обратно в файл. Уже заполненные координаты пропускает — скрипт можно
перезапускать.

Перед запросом адрес нормализуется: этаж и офис срезаются; строение и корпус
оставляются для DaData и срезаются для Nominatim. В справочнике полный адрес
не меняется.

Частоту запросов ограничивает ``geopy.extra.rate_limiter.RateLimiter``.

Провайдер задаётся ``GEOCODER_PROVIDER`` или аргументом ``--provider``.

Запуск:
    uv run python scripts/geocode_branches.py
    uv run python scripts/geocode_branches.py --city sankt-peterburg
    uv run python scripts/geocode_branches.py --provider nominatim --dry-run
    uv run python scripts/geocode_branches.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.directory_service.address import extract_own_city, normalize_for_geocoder
from app.services.directory_service.geocoders.dadata import (
    DadataCleanerGeocoder,
    DadataSuggestionsGeocoder,
)
from app.services.directory_service.geocoders.nominatim import NominatimGeocoder
from geopy.extra.rate_limiter import RateLimiter

#: Сколько первых подряд промахов считать признаком отказа провайдера.
EARLY_MISS_ABORT = 3

_PROVIDER_CHOICES = ("dadata", "dadata_cleaner", "nominatim")
_DADATA_PROVIDERS = frozenset({"dadata", "dadata_cleaner"})


class ProviderLikelyRejected(Exception):
    """Первые запросы к геокодеру все вернули None — дальше гонять бессмысленно."""


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки.

    Возвращает:
        Разобранные аргументы ``--city``, ``--dry-run``, ``--force``, ``--provider``.
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
    parser.add_argument(
        "--provider",
        type=str,
        choices=_PROVIDER_CHOICES,
        default=None,
        help=(
            "Геокодер: dadata (подсказки), dadata_cleaner или nominatim "
            "(по умолчанию из GEOCODER_PROVIDER)"
        ),
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


def make_geocoder(provider: str) -> Any:
    """
    Создаёт клиент выбранного провайдера.

    Аргументы:
        provider: ``dadata``, ``dadata_cleaner`` или ``nominatim``.

    Возвращает:
        Экземпляр геокодера.
    """
    if provider == "dadata":
        return DadataSuggestionsGeocoder()
    if provider == "dadata_cleaner":
        return DadataCleanerGeocoder()
    if provider == "nominatim":
        return NominatimGeocoder()
    raise RuntimeError(
        f"Неизвестный провайдер: {provider!r}. Доступны: {', '.join(_PROVIDER_CHOICES)}."
    )


def process_city(
    path: Path,
    geocode: Any,
    *,
    provider: str,
    client: Any,
    dry_run: bool,
    force: bool,
    only_missing: bool,
) -> tuple[int, int, int]:
    """Обрабатывает один файл города.

    Аргументы:
        path: путь к JSON города.
        geocode: функция геокодинга (уже с RateLimiter и ранним стопом).
        provider: имя провайдера для вывода.
        client: экземпляр геокодера (для чтения ``last_qc_geo`` у DaData).
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
    strip_building = provider not in _DADATA_PROVIDERS

    for branch in city.get("branches", {}).get("items", []):
        if not should_process(branch, force=force, only_missing=only_missing):
            continue
        processed += 1
        address = branch.get("address") or ""
        cleaned = normalize_for_geocoder(address, strip_building=strip_building)
        own_city = extract_own_city(cleaned)
        # Чужой населённый пункт — без ограничения по городу файла;
        # совпадение с городом файла ограничение сохраняет.
        query_city = (
            None
            if own_city is not None and own_city.casefold() != city_title.casefold()
            else city_title
        )
        query = client.build_query(cleaned, query_city)
        point = geocode(query, city=query_city)
        if point is None:
            missed += 1
            print(f"  miss  [{provider}] {city_title}: {address}")
            if query != address:
                print(f"         запрос: {query}")
            continue
        lat, lon = point
        qc_part = ""
        if provider in _DADATA_PROVIDERS:
            qc_geo = getattr(client, "last_qc_geo", None)
            if qc_geo is not None:
                qc_part = f" qc_geo={qc_geo}"
        print(f"  ok    [{provider}{qc_part}] {city_title}: {address} -> {lat:.6f}, {lon:.6f}")
        if query != address:
            print(f"         запрос: {query}")
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
    provider = (args.provider or settings.geocoder_provider).strip().lower()
    if provider not in _PROVIDER_CHOICES:
        print(
            f"Неизвестный GEOCODER_PROVIDER: {provider!r}. "
            f"Доступны: {', '.join(_PROVIDER_CHOICES)}."
        )
        sys.exit(1)

    if provider == "nominatim" and not settings.geocoder_contact.strip():
        print(
            "Не задан GEOCODER_CONTACT. Nominatim требует реальный e-mail или "
            "адрес сайта в переменной окружения — без него запросы отклоняются."
        )
        sys.exit(1)

    only_missing = False if args.force else args.only_missing
    data_dir = settings.directory_data_dir
    files = city_files(data_dir, args.city)
    if not files:
        target = args.city or str(data_dir)
        print(f"Файлов городов не найдено: {target}")
        return

    client = make_geocoder(provider)
    geocode = RateLimiter(
        client.geocode_sync,
        min_delay_seconds=settings.geocoder_pause,
    )

    first_hits: list[bool] = []

    def geocode_with_early_abort(query: str, city: str | None = None) -> tuple[float, float] | None:
        """Вызывает геокодер; при полном прогоне прерывает после трёх первых промахов.

        В режиме только пустых координат ранний стоп отключён: оставшиеся адреса
        как раз трудные, и три промаха подряд не означают отказ провайдера.
        """
        point = geocode(query, city=city)
        if only_missing:
            return point
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
                provider=provider,
                client=client,
                dry_run=args.dry_run,
                force=args.force,
                only_missing=only_missing,
            )
            total_processed += processed
            total_filled += filled
            total_missed += missed
    except ProviderLikelyRejected:
        if provider == "dadata":
            hint = "Проверьте DADATA_API_KEY и лимит Подсказок."
        elif provider == "dadata_cleaner":
            hint = "Проверьте DADATA_API_KEY и DADATA_SECRET_KEY."
        else:
            hint = "Проверьте GEOCODER_CONTACT и политику Nominatim."
        print(
            "Провайдер, судя по всему, отклоняет запросы: первые "
            f"{EARLY_MISS_ABORT} обращения вернули пустой ответ. "
            f"{hint} Прогон прерван."
        )
        sys.exit(1)

    print(
        f"Итого: обработано {total_processed} / "
        f"проставлено {total_filled} / не найдено {total_missed}"
    )


if __name__ == "__main__":
    main()
