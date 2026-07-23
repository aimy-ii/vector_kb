"""Заполнение разделов справочника по сырому тексту страниц.

Заполняет `tariffs`, `categories`, `fleet`, `theory_formats`; вопросы складывает в `_review`.
Города, собранные вручную (нет файла в raw), пропускает не трогая.
Пути передаются параметрами (по умолчанию — из настроек).

Два урока с прошлых заходов зашиты сюда:

* Текст со страниц содержит неразрывные пробелы, поэтому перед поиском всё нормализуется.
  Без этого часть блоков не находилась на ровном месте.
* Категорию у цены первого экрана определять НЕЛЬЗЯ: на странице она рядом не написана,
  а ближайшая карточка категории относится к другому курсу. Поле остаётся пустым осознанно.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import settings

HERO_RE = re.compile(r"(Специальная цена|Курс Базовый)\s*от\s*([\d ]+)\s*₽")
RETRAIN_RE = re.compile(r"Узнать цену\s*от\s*6\s*000\s*₽|от\s*6\s*000\s*₽\s*Узнать цену")
PROMO_AMOUNTS = {1000, 2000, 3000, 4500, 5000}
PROMO_MARKERS = ("студенческим", "Скидка", "Успей вернуть")

CARD_RE = re.compile(r"^Категори[яи]\s*[«\"']?\s*([ABCDАВСD])[»\"']?\s*$", re.IGNORECASE)
DURATION_RE = re.compile(r"([\d]+(?:[,.]\d)?)\s*месяц\w*\s*обучени\w*|обучение от\s*(\d+)\s*месяц")
SEATS_RE = re.compile(r"(\d+)\s*мест")
CYRILLIC_TO_LATIN = {"А": "A", "В": "B", "С": "C", "Д": "D"}

MKPP_RE = re.compile(r"МКПП:\s*([^\n]+)")
AKPP_RE = re.compile(r"АКПП:\s*([^\n]+)")
FLEET_YEAR_RE = re.compile(r"автопарк не старше (\d{4})\s*г")
GALLERY_YEAR_RE = re.compile(r"учебные авто не старше (\d{4}) года")
PREMIUM_RE = re.compile(r"автомобилях премиум-класса:\s*([^\n]+)")
MOTO_RE = re.compile(r"Категория А\s*[-–—]\s*([^\n]+)")
TRUCK_RE = re.compile(r"Автомобиль\s+(газон[^\n]*)", re.IGNORECASE)

THESES = (("fleet_thesis_akpp_price", "Цена обучения на автомате и механике равны", 210),)

THEORY_BLOCKS = (
    ("theory_offline", "Изучай теорию в современных классах", 230),
    (
        "theory_formats_all",
        "Теорию можно изучать в очном, заочном или комбинированных форматах",
        200,
    ),
    ("theory_online", "С помощью нашего фирменного мобильного приложения", 190),
    ("theory_app", "Всё для твоего комфорта", 260),
    ("theory_app_free", "Бесплатно для всех учеников нашей автошколы", 0),
)


def normalize(text: str) -> str:
    """Приводит пробелы к обычным.

    Страницы собраны в Tilda и напичканы неразрывными и узкими пробелами. Поиск по
    подстроке об них спотыкается, поэтому нормализуем перед любым разбором.

    Аргументы:
        text: исходный текст страницы.

    Возвращает:
        Текст, где все виды пробелов заменены на обычный.
    """
    for space in ("\u00a0", "\u202f", "\u2009", "\u2007"):
        text = text.replace(space, " ")
    return text


def _models(raw: str) -> list[str]:
    """Разбивает перечисление машин на отдельные модели."""
    parts = re.split(r"[,;]", raw)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _fragment(text: str, needle: str, after: int) -> str | None:
    """Возвращает опорную фразу вместе с продолжением, схлопнув пробелы.

    Аргументы:
        text: нормализованный текст страницы.
        needle: фраза, с которой начинается нужный кусок.
        after: сколько символов захватить справа.

    Возвращает:
        Фрагмент или None, если фразы на странице нет.
    """
    index = text.find(needle)
    if index == -1:
        return None
    return " ".join(text[index : min(len(text), index + len(needle) + after)].split())


def build_tariffs(prices: list[dict], url: str) -> tuple[list[dict], list[str]]:
    """Раскладывает найденные суммы по тарифам.

    Аргументы:
        prices: содержимое `tariffs.prices_found`.
        url: адрес страницы.

    Возвращает:
        Пару (тарифы, замечания).
    """
    tariffs: list[dict] = []
    notes: list[str] = []

    for item in prices:
        price = item["price"]
        context = normalize(item["context"])
        if price in PROMO_AMOUNTS or any(m in context for m in PROMO_MARKERS):
            continue

        hero = HERO_RE.search(context)
        if hero:
            label = hero.group(1)
            shown = f"{price:,}".replace(",", " ")
            tariffs.append(
                {
                    "id": "tariff_hero",
                    "name": "Базовый" if label == "Курс Базовый" else None,
                    "category": None,
                    "price": price,
                    "price_is_from": item["price_is_from"],
                    "price_note": (
                        f"«{label} от {shown} ₽*», сноска «*подробности у менеджера»; "
                        "категория рядом с ценой на странице не указана"
                    ),
                    "duration": None,
                    "practice_hours": None,
                    "includes": [],
                    "start_frequency": None,
                    "valid_until": None,
                    "_source": url,
                }
            )
            continue

        if RETRAIN_RE.search(context):
            tariffs.append(
                {
                    "id": "tariff_card_6000",
                    "name": None,
                    "category": None,
                    "price": price,
                    "price_is_from": True,
                    "price_note": (
                        "«от 6 000 ₽» в карточке рядом с кнопкой «Узнать цену»; "
                        "к какой карточке относится — из текста страницы не видно"
                    ),
                    "duration": None,
                    "practice_hours": None,
                    "includes": [],
                    "start_frequency": None,
                    "valid_until": None,
                    "_source": url,
                }
            )
            notes.append("tariffs.tariff_card_6000: определить категорию карточки в браузере")
            continue

        notes.append(f"tariffs: сумма {price} не опознана — {context[:70]}")

    return tariffs, notes


def build_categories(lines: list[str], url: str) -> list[dict]:
    """Собирает карточки категорий: срок обучения, частота стартов, что в карточке.

    Карточка в плоском тексте выглядит как несколько строк вокруг заголовка
    «Категория В»: срок, строка про коробку, «Старт каждые» и число дней.

    Аргументы:
        lines: строки нормализованного текста страницы.
        url: адрес страницы.

    Возвращает:
        Список категорий в схеме `categories.items`.
    """
    items: list[dict] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        match = CARD_RE.match(line.strip())
        if not match:
            continue
        letter = CYRILLIC_TO_LATIN.get(match.group(1).upper(), match.group(1).upper())
        if letter in seen:
            continue
        seen.add(letter)

        window = lines[max(0, index - 8) : min(len(lines), index + 9)]
        duration = None
        start = None
        seats = None
        includes = []

        for offset, near in enumerate(window):
            near = near.strip()
            hit = DURATION_RE.search(near)
            if hit and duration is None:
                duration = near
            if "Старт каждые" in near:
                tail = window[offset + 1].strip() if offset + 1 < len(window) else ""
                start = f"Старт каждые {tail}".strip() if tail else "Старт каждые"
            if "В группе осталось" in near:
                tail = window[offset + 1].strip() if offset + 1 < len(window) else ""
                found = SEATS_RE.search(tail)
                if found:
                    seats = int(found.group(1))
            if "|" in near and len(near) < 60:
                includes.append(near)

        items.append(
            {
                "id": f"cat_{letter.lower()}",
                "code": letter,
                "name": line.strip(),
                "price": None,
                "price_note": "цена в карточке не указана, кнопка «Узнать цену»",
                "duration": duration,
                "start_frequency": start,
                "seats_left": seats,
                "includes": includes,
                "_source": url,
            }
        )
    return items


def build_fleet(text: str, url: str) -> tuple[list[dict], list[str]]:
    """Собирает автопарк и тезисы про коробку передач.

    Аргументы:
        text: нормализованный текст страницы.
        url: адрес страницы.

    Возвращает:
        Пару (записи, замечания).
    """
    items: list[dict] = []
    notes: list[str] = []

    year_match = FLEET_YEAR_RE.search(text)
    year = f"не старше {year_match.group(1)} г" if year_match else None
    mkpp = MKPP_RE.findall(text)
    akpp = AKPP_RE.findall(text)

    for kind, found, gear in (("fleet_b_mkpp", mkpp, "МКПП"), ("fleet_b_akpp", akpp, "АКПП")):
        if not found:
            continue
        items.append(
            {
                "id": kind,
                "kind": "vehicles",
                "category": "B",
                "transmission": gear,
                "models": _models(found[0]),
                "year": year,
                "text": f"{gear}: {found[0].strip()}",
                "_source": url,
            }
        )

    if len(set(mkpp)) > 1 or len(set(akpp)) > 1:
        notes.append("fleet: списки машин на странице расходятся между блоками — сверить")

    moto = MOTO_RE.search(text)
    if moto:
        items.append(
            {
                "id": "fleet_a_moto",
                "kind": "vehicles",
                "category": "A",
                "transmission": None,
                "models": _models(moto.group(1)),
                "year": None,
                "text": f"Категория А - {moto.group(1).strip()}",
                "_source": url,
            }
        )

    truck = TRUCK_RE.search(text)
    if truck:
        items.append(
            {
                "id": "fleet_c_truck",
                "kind": "vehicles",
                "category": "C",
                "transmission": None,
                "models": [],
                "year": None,
                "text": f"Автомобиль {truck.group(1).strip()}",
                "_source": url,
            }
        )

    premium = PREMIUM_RE.search(text)
    if premium:
        items.append(
            {
                "id": "fleet_premium",
                "kind": "vehicles",
                "category": None,
                "transmission": None,
                "models": _models(premium.group(1)),
                "year": None,
                "text": f"Максимум комфорта в обучении на автомобилях премиум-класса: "
                f"{premium.group(1).strip()}",
                "_source": url,
            }
        )

    gallery = GALLERY_YEAR_RE.search(text)
    if gallery:
        items.append(
            {
                "id": "fleet_gallery_year",
                "kind": "thesis",
                "category": None,
                "transmission": None,
                "models": [],
                "year": f"не старше {gallery.group(1)} года",
                "text": f"Комфортные учебные авто не старше {gallery.group(1)} года",
                "_source": url,
            }
        )

    for thesis_id, needle, after in THESES:
        fragment = _fragment(text, needle, after)
        if fragment:
            items.append(
                {
                    "id": thesis_id,
                    "kind": "thesis",
                    "category": None,
                    "transmission": None,
                    "models": [],
                    "year": None,
                    "text": fragment,
                    "_source": url,
                }
            )

    if not any(i["kind"] == "vehicles" for i in items):
        notes.append("fleet: списка машин на странице нет — этот город без блока автопарка")
    return items, notes


def build_theory(text: str, url: str) -> tuple[list[dict], list[str]]:
    """Собирает блоки про форматы теории.

    Аргументы:
        text: нормализованный текст страницы.
        url: адрес страницы.

    Возвращает:
        Пару (записи, замечания).
    """
    items = []
    for block_id, needle, after in THEORY_BLOCKS:
        fragment = _fragment(text, needle, after)
        if fragment:
            items.append(
                {"id": block_id, "name": None, "surcharge": None, "text": fragment, "_source": url}
            )
    notes = (
        ["theory_formats: доплата за комбинированный формат на странице не указана"]
        if items
        else ["theory_formats: блоков про теорию на странице нет"]
    )
    return items, notes


def run(
    *,
    out_dir: Path | None = None,
    raw_dir: Path | None = None,
) -> int:
    """Проходит по всем городам и заполняет разделы.

    Args:
        out_dir: каталог собранных JSON.
        raw_dir: каталог сырых страниц.

    Returns:
        Код возврата процесса.
    """
    out = out_dir if out_dir is not None else settings.out_dir
    raw = raw_dir if raw_dir is not None else settings.raw_dir
    files = sorted(p for p in out.glob("*.json") if p.stem != "_index")
    if not files:
        print(f"Не найдено *.json в {out} — сначала запусти сбор страниц")
        return 1

    print(f"{'город':20s} {'цена':>8s} {'кат.':>5s} {'срок':>12s} {'парк':>5s} {'теор':>5s}")
    print("-" * 62)
    skipped = 0

    for path in files:
        city = json.loads(path.read_text(encoding="utf-8"))
        slug = city["meta"]["city_slug"]
        raw_path = raw / f"{slug}.txt"
        if not raw_path.exists():
            skipped += 1
            continue

        page_text = normalize(raw_path.read_text(encoding="utf-8"))
        lines = page_text.split("\n")
        url = city["tariffs"].get("_source") or city["branches"]["_source"]

        tariffs, tariff_notes = build_tariffs(city["tariffs"].get("prices_found", []), url)
        categories = build_categories(lines, url)
        fleet, fleet_notes = build_fleet(page_text, url)
        theory, theory_notes = build_theory(page_text, url)

        for section, values in (
            ("tariffs", tariffs),
            ("categories", categories),
            ("fleet", fleet),
            ("theory_formats", theory),
        ):
            city.setdefault(section, {"_source": url})["items"] = values

        keep = [
            n
            for n in city.get("_review", [])
            if not n.startswith(("tariffs", "fleet", "theory_formats", "categories"))
        ]
        city["_review"] = keep + tariff_notes + fleet_notes + theory_notes
        path.write_text(json.dumps(city, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        hero = next((t for t in tariffs if t["id"] == "tariff_hero"), None)
        price = f"{hero['price']:,}".replace(",", " ") if hero else "—"
        base = next((c for c in categories if c["code"] == "B"), None)
        duration = (base["duration"] or "?") if base else "нет карточки"
        print(
            f"{slug:20s} {price:>8s} {len(categories):>5d} {duration[:12]:>12s} "
            f"{len(fleet):>5d} {len(theory):>5d}"
        )

    print(f"\nГотово. Пропущено собранных вручную: {skipped}. Вопросы — в поле _review.")
    return 0
