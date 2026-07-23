"""Полный прогон пайплайна обновления справочника."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from app.constants.parsing import PARSE_LOG_PREFIX
from app.core.config import settings
from app.services.directory_service import directory_store
from app.services.parsing_service import (
    finalize,
    index,
    package_data,
    scrape,
    sections,
)

logger = logging.getLogger(__name__)


def run(
    *,
    only: list[str] | None = None,
    force: bool = False,
    include_external: bool = False,
    raw_dir: Path | None = None,
    out_dir: Path | None = None,
    directory_data_dir: Path | None = None,
    index_path: Path | None = None,
    landmarks_path: Path | None = None,
    on_step: Callable[[str], None] | None = None,
    on_city_done: Callable[[int], None] | None = None,
) -> None:
    """
    Выполняет полный прогон: сбор → разделы → финализация → индекс → пакет.

    При успехе сбрасывает кэш справочника в памяти. При ошибке на любом шаге
    поднимает исключение, данные в памяти остаются прежними.

    Args:
        only: слаги городов для ограниченного обхода.
        force: игнорировать кэш сырых страниц.
        include_external: включать города на чужих доменах.
        raw_dir: каталог сырых страниц.
        out_dir: каталог собранных JSON.
        directory_data_dir: каталог урезанных данных справочника.
        index_path: путь к файлу индекса.
        landmarks_path: путь к landmarks.json.
        on_step: колбэк с именем текущего шага.
        on_city_done: колбэк с числом обработанных городов.
    """
    raw = raw_dir if raw_dir is not None else settings.raw_dir
    out = out_dir if out_dir is not None else settings.out_dir
    directory_dir = (
        directory_data_dir if directory_data_dir is not None else settings.directory_data_dir
    )
    index_file = index_path if index_path is not None else settings.index_path
    landmarks = landmarks_path if landmarks_path is not None else settings.landmarks_path

    def _step(name: str) -> None:
        logger.info("%s Шаг: %s", PARSE_LOG_PREFIX, name)
        if on_step is not None:
            on_step(name)

    _step("fetch")
    code = scrape.run(
        only=only,
        force=force,
        include_external=include_external,
        include_done=True,
        raw_dir=raw,
        out_dir=out,
        on_city_done=on_city_done,
    )
    if code != 0:
        raise RuntimeError("Сбор страниц завершился с ошибками")

    _step("sections")
    if sections.run(out_dir=out, raw_dir=raw) != 0:
        raise RuntimeError("Заполнение разделов завершилось с ошибкой")

    _step("finalize")
    if finalize.run(out_dir=out, landmarks_path=landmarks) != 0:
        raise RuntimeError("Финализация завершилась с ошибкой")

    _step("index")
    if index.run(out_dir=out, index_path=index_file) != 0:
        raise RuntimeError("Сборка индекса завершилась с ошибкой")

    _step("package_data")
    if package_data.run(src_dir=out, dst_dir=directory_dir) != 0:
        raise RuntimeError("Сборка данных справочника завершилась с ошибкой")

    _step("reload")
    directory_store.reload(data_dir=directory_dir)
    logger.info("%s Пайплайн завершён, справочник перечитан", PARSE_LOG_PREFIX)
