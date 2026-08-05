"""Проверка целостности координат в файлах справочника."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.directory_service.coords_integrity import (
    MAX_BRANCH_FROM_CITY_KM,
    branches_far_from_city_center,
    duplicate_addresses_across_cities,
    duplicate_coordinates,
    normalize_address_key,
)

_COMMA_AFTER_ABBR = re.compile(r"\b(ул|пр|пер|б-р|наб|ш|пл|д|стр|корп)\s*,\s*(?=\S)")

#: Ожидаемое число филиалов после удаления кросс-городских дублей.
_EXPECTED_BRANCH_COUNT = 212


def _load_cities() -> list[dict[str, Any]]:
    """Читает все JSON городов справочника."""
    data_dir: Path = settings.directory_data_dir
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(data_dir.glob("*.json"))
    ]


def test_all_branches_have_lat_lon_keys() -> None:
    """У каждого филиала во всех городах присутствуют ключи lat и lon."""
    data_dir: Path = settings.directory_data_dir
    files = sorted(data_dir.glob("*.json"))
    assert len(files) == 41
    branch_count = 0
    for path in files:
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            branch_count += 1
            assert "lat" in branch, f"{path.name}: {branch.get('id')} без lat"
            assert "lon" in branch, f"{path.name}: {branch.get('id')} без lon"
    assert branch_count == _EXPECTED_BRANCH_COUNT


def test_no_comma_after_street_abbreviation() -> None:
    """Ни в одном адресе нет запятой сразу после сокращения улицы или дома."""
    data_dir: Path = settings.directory_data_dir
    bad: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            address = branch.get("address") or ""
            if _COMMA_AFTER_ABBR.search(address):
                bad.append(f"{path.name}: {branch.get('id')}: {address}")
    assert bad == []


_FORBIDDEN_ADDRESS_MARKERS = (
    "Время работы",
    "Перерыв",
    "Режим работы",
    "Телефон",
)


def test_addresses_have_no_schedule_or_phone_markers() -> None:
    """В address нет подписей расписания/телефона и переводов строки."""
    data_dir: Path = settings.directory_data_dir
    bad: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            address = branch.get("address") or ""
            if "\n" in address or "\r" in address:
                bad.append(f"{path.name}: {branch.get('id')}: перевод строки")
                continue
            for marker in _FORBIDDEN_ADDRESS_MARKERS:
                if marker.casefold() in address.casefold():
                    bad.append(f"{path.name}: {branch.get('id')}: {address!r}")
                    break
    assert bad == []


def test_all_branches_have_filled_coords() -> None:
    """У всех филиалов lat/lon заполнены."""
    data_dir: Path = settings.directory_data_dir
    missing: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            branch_id = branch.get("id") or ""
            if branch.get("lat") is None or branch.get("lon") is None:
                missing.append(f"{path.name}: {branch_id}")
    assert missing == [], f"пустые координаты: {missing}"


def test_all_cities_have_meta_coords() -> None:
    """У всех городов в meta заполнены координаты центра."""
    data_dir: Path = settings.directory_data_dir
    missing: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        meta = city.get("meta") or {}
        if meta.get("lat") is None or meta.get("lon") is None:
            missing.append(path.name)
    assert missing == [], f"города без meta.lat/lon: {missing}"


def test_branch_coords_within_city_radius() -> None:
    """Координаты филиала не дальше порога от центра своего города."""
    data_dir: Path = settings.directory_data_dir
    bad: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        city_name = (city.get("meta") or {}).get("city", path.stem)
        for branch_id, distance in branches_far_from_city_center(city):
            bad.append(f"{city_name}: {branch_id}: {distance:.1f} км")
    assert bad == [], f"филиалы дальше {MAX_BRANCH_FROM_CITY_KM} км от центра города: {bad}"


def test_no_duplicate_addresses_across_cities() -> None:
    """Один и тот же адрес не встречается в файлах разных городов."""
    duplicates = duplicate_addresses_across_cities(_load_cities())
    assert duplicates == [], f"дубли адресов между городами: {duplicates}"


def test_no_duplicate_coordinates() -> None:
    """Две записи не имеют точно одинаковых lat/lon."""
    duplicates = duplicate_coordinates(_load_cities())
    assert duplicates == [], f"скопированные координаты: {duplicates}"


def test_normalize_address_key_ignores_abbr_and_case() -> None:
    """Ключ сравнения схлопывает регистр, пробелы и сокращения ул./д."""
    assert normalize_address_key("ул. Кирова, 23, 2 этаж, офис 6") == normalize_address_key(
        "Кирова 23"
    )
    assert normalize_address_key("проспект Красного Знамени, д. 51А офис 307") == (
        normalize_address_key("проспект Красного Знамени 51А")
    )


def _sample_city(
    *,
    city_lat: float,
    city_lon: float,
    branch_lat: float,
    branch_lon: float,
    address: str,
) -> dict[str, Any]:
    """Минимальный город для unit-тестов проверки расстояния."""
    return {
        "meta": {"city": "Тестоград", "lat": city_lat, "lon": city_lon},
        "branches": {
            "items": [
                {
                    "id": "test_branch",
                    "address": address,
                    "lat": branch_lat,
                    "lon": branch_lon,
                }
            ]
        },
    }


def test_far_branch_from_city_center_is_detected() -> None:
    """Филиал дальше порога от центра города попадает в список нарушений."""
    # Центр Москвы → точка ~61 км севернее.
    city = _sample_city(
        city_lat=55.75,
        city_lon=37.62,
        branch_lat=56.30,
        branch_lon=37.62,
        address="ул. Ленина, 1",
    )
    far = branches_far_from_city_center(city, max_km=50.0)
    assert len(far) == 1
    assert far[0][0] == "test_branch"
    assert far[0][1] > 50.0


def test_own_city_branch_excluded_from_distance_check() -> None:
    """Филиал с собственным населённым пунктом в адресе из проверки исключён."""
    city = _sample_city(
        city_lat=54.98,
        city_lon=73.37,
        branch_lat=55.43,
        branch_lon=74.94,
        address="Р.П. Оконешниково, ул. Калинина 25",
    )
    assert branches_far_from_city_center(city, max_km=50.0) == []


def test_duplicate_address_helper_detects_cross_city() -> None:
    """Хелпер ловит одинаковый адрес в двух городах."""
    cities = [
        {
            "meta": {"city": "А"},
            "branches": {"items": [{"id": "a1", "address": "ул. Кирова, 23"}]},
        },
        {
            "meta": {"city": "Б"},
            "branches": {"items": [{"id": "b1", "address": "Кирова 23"}]},
        },
    ]
    found = duplicate_addresses_across_cities(cities)
    assert len(found) == 1
    assert found[0][1] == ["А:a1", "Б:b1"]


def test_duplicate_coordinates_helper_detects_copy() -> None:
    """Хелпер ловит точное совпадение lat/lon у разных записей."""
    cities = [
        {
            "meta": {"city": "А"},
            "branches": {"items": [{"id": "a1", "address": "ул. А, 1", "lat": 1.0, "lon": 2.0}]},
        },
        {
            "meta": {"city": "Б"},
            "branches": {"items": [{"id": "b1", "address": "ул. Б, 2", "lat": 1.0, "lon": 2.0}]},
        },
    ]
    found = duplicate_coordinates(cities)
    assert len(found) == 1
    assert found[0][0] == (1.0, 2.0)
    assert found[0][1] == ["А:a1", "Б:b1"]
