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
    assert branch_count == 235


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
