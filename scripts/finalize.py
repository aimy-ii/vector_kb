"""Финализация справочника: плоские ключи филиалов и обогащение.

Запуск из корня проекта:

    uv run python scripts/finalize.py            # слаги + ориентиры + тип точки
    uv run python scripts/finalize.py --metro    # плюс метро и район с avtoshkoli.ru

Что делает:

    1. Переписывает идентификаторы филиалов в глобально уникальные плоские ключи вида
   `perm_chernyshevskogo`. Прежние `branch_01` были уникальны только внутри города,
   а нам нужен один ключ на всю сеть.
2. Подставляет ориентир (ТЦ, ЖК, БЦ) и тип точки из `landmarks.json` — выгрузки 2ГИС.
3. По флагу `--metro` тянет станции метро и район с avtoshkoli.ru, где они подписаны
   у каждого филиала.

Ничего не выдумывает: не нашлось — остаётся `null`, город попадает в отчёт.
Пути к данным считаются от корня проекта, а не от каталога скрипта.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "out"
LANDMARKS = ROOT / "landmarks.json"

TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

STREET_WORDS = re.compile(
    r"\b(улица|ул|проспект|просп|пр-кт|пр|площадь|пл|шоссе|бульвар|переулок|пер|"
    r"тракт|микрорайон|мкр|дом|д|корпус|корп|к|литер|лит|этаж|эт|офис|оф|помещ|пом|стр|ст)\b",
    re.I,
)

# Слаги городов на avtoshkoli.ru, где они расходятся с нашими.
METRO_SLUG = {
    "sankt-peterburg": "sankt-peterburg",
    "novosib": "novosibirsk",
    "tagil": "nizhniy-tagil",
    "kyrgan": "kurgan",
    "tyumen": "tyumen",
    "eletz": "elets",
    "dagomyc": "sochi",
    "kalachinsk": "omsk",
    "kormilovka": "omsk",
}


def translit(text: str) -> str:
    """Переводит русскую строку в латиницу для слага.

    Аргументы:
        text: исходная строка.

    Возвращает:
        Строку из латинских букв, цифр и подчёркиваний.
    """
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    result = "".join(TRANSLIT.get(ch, ch if ch.isalnum() else " ") for ch in text)
    return re.sub(r"\s+", "_", result.strip())


def street_of(address: str) -> str:
    """Достаёт из адреса название улицы без служебных слов и номеров.

    Аргументы:
        address: адрес филиала как на сайте.

    Возвращает:
        Название улицы в нижнем регистре или пустую строку.
    """
    head = address.split("(")[0]
    head = re.sub(r"\d+[^\s,]*", " ", head)
    head = STREET_WORDS.sub(" ", head)
    head = re.sub(r"[^\w\s-]", " ", head)
    words = [w for w in head.split() if len(w) > 2 and w.lower() not in {"город", "эт"}]
    return " ".join(words[:2]).lower() if words else ""


def house_of(address: str) -> str:
    """Достаёт номер дома для сопоставления с 2ГИС.

    Аргументы:
        address: адрес филиала.

    Возвращает:
        Номер дома в нижнем регистре без корпусов и литер.
    """
    match = re.search(r"(\d+(?:/\d+)?)", address)
    return match.group(1) if match else ""


def make_slug(city_slug: str, address: str, taken: set[str], order: int) -> str:
    """Собирает плоский уникальный ключ филиала.

    Аргументы:
        city_slug: слаг города.
        address: адрес филиала.
        taken: уже занятые ключи.
        order: порядковый номер филиала, нужен для запасного варианта.

    Возвращает:
        Ключ вида `perm_chernyshevskogo`, уникальный в пределах всей сети.
    """
    base = translit(street_of(address)) or f"branch_{order:02d}"
    key = f"{city_slug}_{base}"
    if key not in taken:
        taken.add(key)
        return key
    house = house_of(address)
    candidate = f"{key}_{house}" if house else f"{key}_{order:02d}"
    while candidate in taken:
        order += 1
        candidate = f"{key}_{order:02d}"
    taken.add(candidate)
    return candidate


def load_landmarks() -> list[dict]:
    """Читает выгрузку ориентиров и типов точек из 2ГИС."""
    if not LANDMARKS.exists():
        return []
    return json.loads(LANDMARKS.read_text(encoding="utf-8"))


def match_landmark(city_name: str, address: str, rows: list[dict]) -> dict | None:
    """Ищет ориентир и тип точки по названию улицы и номеру дома.

    Аргументы:
        city_name: название города как на сайте.
        address: адрес филиала.
        rows: записи из `landmarks.json`.

    Возвращает:
        Найденную запись или None.
    """
    site_street = street_of(address).split()[-1] if street_of(address) else ""
    site_house = house_of(address)
    if not site_street:
        return None
    for row in rows:
        if row["город"] != city_name:
            continue
        gis_street = street_of(row["улица"])
        if not gis_street or site_street not in gis_street:
            continue
        if house_of(row["дом"]) == site_house:
            return row
    return None


def fetch_metro(city_slug: str) -> dict[str, dict]:
    """Тянет метро и район по филиалам города с avtoshkoli.ru.

    Аргументы:
        city_slug: слаг города в нашем справочнике.

    Возвращает:
        Словарь «улица+дом → {метро, район}». Пустой, если страница недоступна.
    """
    import httpx

    slug = METRO_SLUG.get(city_slug, city_slug)
    url = f"https://avtoshkoli.ru/{slug}/avtoshkola-vektor/"
    try:
        response = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ru-RU,ru;q=0.9"},
        )
        response.raise_for_status()
    except Exception:  # noqa: BLE001 — недоступность города не должна ронять проход
        return {}

    text = re.sub(r"<[^>]+>", " ", response.text)
    text = re.sub(r"\s+", " ", text)
    found: dict[str, dict] = {}
    pattern = re.compile(
        r"(?:ул\.|улица|пр-т|проспект|пл\.|площадь)\s*([А-ЯЁа-яё\s-]{3,30}?),?\s*"
        r"(\d+(?:/\d+)?)[^А-ЯЁ]{0,40}?(?:Метро:\s*([^·|<]{3,60}))?",
    )
    for match in pattern.finditer(text):
        street, house, metro = match.group(1), match.group(2), match.group(3)
        key = f"{translit(street.strip())}_{house}"
        if metro:
            found[key] = {"метро": [m.strip() for m in metro.split(",") if m.strip()]}
    return found


def main() -> int:
    """Проходит по городам, переписывает ключи и обогащает филиалы.

    Возвращает:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(prog="finalize")
    parser.add_argument("--metro", action="store_true", help="тянуть метро с avtoshkoli.ru")
    args = parser.parse_args()

    rows = load_landmarks()
    if not rows:
        print("Нет landmarks.json — ориентиры и тип точки проставлены не будут.")

    files = sorted(p for p in OUT_DIR.glob("*.json") if p.stem != "_index")
    taken: set[str] = set()
    stats = {"филиалов": 0, "ориентир": 0, "тип": 0, "метро": 0}
    no_metro: list[str] = []

    print(f"{'город':20s} {'филиалов':>9s} {'ориентир':>9s} {'тип':>5s} {'метро':>6s}")
    print("-" * 55)

    for path in files:
        city = json.loads(path.read_text(encoding="utf-8"))
        slug = city["meta"]["city_slug"]
        name = city["meta"]["city"]

        metro_map = fetch_metro(slug) if args.metro else {}
        if args.metro and not metro_map:
            no_metro.append(slug)

        got = {"ориентир": 0, "тип": 0, "метро": 0}
        for order, branch in enumerate(city["branches"]["items"], start=1):
            address = branch["address"]
            branch["id"] = make_slug(slug, address, taken, order)

            hit = match_landmark(name, address, rows)
            branch["landmark"] = hit["ориентир"] if hit else None
            branch["place_type"] = hit["тип"] if hit else None
            if branch["landmark"]:
                got["ориентир"] += 1
            if branch["place_type"]:
                got["тип"] += 1

            words = street_of(address).split()
            key = f"{translit(words[-1]) if words else ''}_{house_of(address)}"
            found = metro_map.get(key)
            branch["metro"] = found["метро"] if found else None
            branch["district"] = branch.get("district")
            if branch["metro"]:
                got["метро"] += 1

        path.write_text(json.dumps(city, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        count = len(city["branches"]["items"])
        stats["филиалов"] += count
        for key in ("ориентир", "тип", "метро"):
            stats[key] += got[key]
        print(f"{slug:20s} {count:>9d} {got['ориентир']:>9d} {got['тип']:>5d} {got['метро']:>6d}")
        if args.metro:
            time.sleep(1.5)

    print(f"\nВсего: {stats}")
    if no_metro:
        print(f"Метро не забралось: {', '.join(no_metro)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
