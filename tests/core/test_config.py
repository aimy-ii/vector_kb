"""Тесты настроек и путей."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.directory_service.loader import load_cities

ROOT = Path(__file__).resolve().parents[2]


def test_default_port_is_8317() -> None:
    """Порт по умолчанию — 8317, восьмитысячный не занят."""
    assert settings.api_port == 8317


def test_geocoder_user_agent_includes_contact(monkeypatch) -> None:
    """geocoder_user_agent собирается из geocoder_contact и содержит контакт."""
    monkeypatch.setattr(settings, "geocoder_contact", "geocoder-tests@localhost")
    assert "geocoder-tests@localhost" in settings.geocoder_user_agent
    assert settings.geocoder_user_agent.startswith("vector-kb/0.1 (")


def test_paths_come_from_settings() -> None:
    """Каталоги данных заданы в настройках и существуют."""
    assert settings.directory_data_dir.is_dir()
    assert settings.landmarks_path.is_file()


def test_directory_data_copied_intact() -> None:
    """В каталоге справочника 41 JSON, загрузка не пустая."""
    files = list(settings.directory_data_dir.glob("*.json"))
    assert len(files) == 41
    cities = load_cities(settings.directory_data_dir)
    assert len(cities) == 41


def test_obsolete_root_files_absent() -> None:
    """Устаревшие файлы в корне удалены."""
    assert not (ROOT / "README_FINAL.md").exists()
    assert not (ROOT / "conftest.py").exists()
    assert not (ROOT / "src" / "vektor_scraper").exists()
    assert not (ROOT / "vektor_directory").exists()
    assert not (ROOT / "fill_demo_data.py").exists()
    assert (ROOT / "scripts" / "fill_demo_data.py").is_file()
