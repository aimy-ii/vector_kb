"""Сбор страниц городов: скачивание, разбор, запись JSON."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from app.constants.parsing import PARSE_LOG_PREFIX
from app.core.config import settings
from app.services.parsing_service import cities as cities_mod
from app.services.parsing_service.fetch import collect_links, fetch_to_disk
from app.services.parsing_service.parse import build

logger = logging.getLogger(__name__)


def run(
    *,
    only: list[str] | None = None,
    force: bool = False,
    include_external: bool = False,
    include_done: bool = True,
    pause: float | None = None,
    raw_dir: Path | None = None,
    out_dir: Path | None = None,
    on_city_done: Callable[[int], None] | None = None,
) -> int:
    """
    Обходит города, сохраняет сырые страницы и JSON.

    Args:
        only: слаги конкретных городов.
        force: перекачивать, игнорируя кэш.
        include_external: включая города на чужих доменах.
        include_done: включая уже собранные вручную.
        pause: пауза между городами; по умолчанию из настроек.
        raw_dir: каталог сырых страниц.
        out_dir: каталог собранных JSON.
        on_city_done: колбэк с числом обработанных городов.

    Returns:
        0 — все города разобраны, 1 — были ошибки.
    """
    raw = raw_dir if raw_dir is not None else settings.raw_dir
    json_dir = out_dir if out_dir is not None else settings.out_dir
    city_pause = pause if pause is not None else settings.parse_pause
    json_dir.mkdir(parents=True, exist_ok=True)

    targets = cities_mod.select(
        include_done=include_done,
        include_external=include_external,
        only=only,
    )
    if not targets:
        logger.info("%s Нечего собирать: список городов пуст", PARSE_LOG_PREFIX)
        return 0

    today = date.today().isoformat()
    failures: list[str] = []
    index: list[dict[str, object]] = []

    logger.info("%s Городов к обходу: %s", PARSE_LOG_PREFIX, len(targets))
    for number, city in enumerate(targets, start=1):
        prefix = f"[{number}/{len(targets)}] {city.name}"
        try:
            html, text = fetch_to_disk(city.slug, city.url, raw, force=force)
            document = build(city.slug, city.name, city.url, text, collect_links(html), today)
            path = json_dir / f"{city.slug}.json"
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            branches = len(document["branches"]["items"])
            promos = len(document["promos"]["items"])
            prices = len(document["tariffs"]["prices_found"])
            conflicts = len(document["conflicts"])
            logger.info(
                "%s %s: филиалов %s, акций %s, сумм %s, расхождений %s → %s",
                PARSE_LOG_PREFIX,
                prefix,
                branches,
                promos,
                prices,
                conflicts,
                path,
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
        except Exception as exc:  # noqa: BLE001 — падение одного города не рвёт обход
            logger.error("%s %s: ОШИБКА — %s", PARSE_LOG_PREFIX, prefix, exc)
            print(f"{prefix}: ОШИБКА — {exc}", file=sys.stderr)
            failures.append(city.slug)
        if on_city_done is not None:
            on_city_done(len(index))
        if number < len(targets):
            time.sleep(city_pause)

    (json_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(
        "%s Готово: %s городов в %s, сырые страницы в %s",
        PARSE_LOG_PREFIX,
        len(index),
        json_dir,
        raw,
    )
    if failures:
        logger.error("%s Не собрались: %s", PARSE_LOG_PREFIX, ", ".join(failures))
        return 1
    return 0
