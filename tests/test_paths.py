"""Проверки раскладки проекта: скрипты, документация, пути к данным."""

from __future__ import annotations

from pathlib import Path

import directory

ROOT = Path(__file__).resolve().parent.parent


def test_pipeline_scripts_exist() -> None:
    """Одноразовые скрипты пайплайна лежат в scripts/."""
    for name in ("finalize.py", "apply_sections.py", "build_index.py"):
        assert (ROOT / "scripts" / name).is_file()


def test_obsolete_root_files_absent() -> None:
    """Устаревшие файлы в корне удалены."""
    assert not (ROOT / "README_FINAL.md").exists()
    assert not (ROOT / "conftest.py").exists()


def test_data_dir_finds_cities_from_project_root() -> None:
    """directory.data_dir() находит каталог с городами из корня проекта."""
    path = directory.data_dir()
    assert path.is_dir()
    cities = [p for p in path.glob("*.json") if not p.stem.startswith("_")]
    assert cities, f"в {path} нет файлов городов"
