"""Проверка целостности координат в файлах справочника."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import settings

_COMMA_AFTER_ABBR = re.compile(r"\b(ул|пр|пер|б-р|наб|ш|пл|д|стр|корп)\s*,\s*(?=\S)")


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
    assert branch_count == 222


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

#: Филиалы, у которых координаты пока намеренно пустые (остаток геокодинга).
#: Adler×2 и Нижняя Омка находятся ретраем без locations — записать отдельным прогоном.
_COORDS_ALLOWED_MISSING: frozenset[str] = frozenset(
    {
        "adler_kirova",
        "adler_urozhaynaya",
        "artem_novoivanovskaya",
        "artem_krasnogo_znamenii",
        "artem_russkaya",
        "artem_admirala_gorshkova",
        "kormilovka_kirova",
        "omsk_petra_nekrasova",
        "omsk_okruzhnaya_doroga",
        "omsk_nizhnyaya_omka",
        "zheleznogorsk_lado_ketshoveli",
    }
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


def test_all_branches_have_coords_except_allowlist() -> None:
    """У всех филиалов, кроме явного списка исключений, lat/lon заполнены."""
    data_dir: Path = settings.directory_data_dir
    missing: list[str] = []
    unexpected: list[str] = []
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            branch_id = branch.get("id") or ""
            empty = branch.get("lat") is None or branch.get("lon") is None
            if empty and branch_id not in _COORDS_ALLOWED_MISSING:
                missing.append(f"{path.name}: {branch_id}")
            if not empty and branch_id in _COORDS_ALLOWED_MISSING:
                unexpected.append(f"{path.name}: {branch_id}")
    assert missing == [], f"пустые координаты вне списка: {missing}"
    assert unexpected == [], f"в списке исключений, но уже заполнены: {unexpected}"
