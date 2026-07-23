"""Справочник автошколы: два списка ключей и две функции по ключу.

Города и филиалы адресуются плоскими слагами. Слаг города — `perm`, слаг филиала —
`perm_chernyshevskogo`, уникальный на всю сеть. Списки отдаются модели как enum,
поэтому пришедший обратно ключ валиден по построению.

Мета намеренно без технических полей: то, что возвращают `get_city` и `get_branch`,
модель пересказывает клиенту своими словами.

Цены в мете нет. Число на сайте занижено примерно вдвое против реальной стоимости
(проверено по сторонним площадкам и отзывам учеников), поэтому вслух оно не идёт.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    """Определяет, откуда читать файлы городов.

    Порядок: переменная окружения `VEKTOR_DATA`, затем `data/out` рядом с модулем
    (так лежит в проекте сбора), затем `data` (так лежит в проекте бота).

    Возвращает:
        Каталог с файлами городов.
    """
    env = os.getenv("VEKTOR_DATA")
    if env:
        return Path(env)
    here = Path(__file__).parent
    for candidate in (here / "data" / "out", here / "data"):
        if candidate.is_dir():
            return candidate
    return here / "data"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    """Читает все файлы городов в память один раз за процесс.

    Возвращает:
        Словарь «слаг города → разобранный файл».
    """
    cities: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir().glob("*.json")):
        if path.stem.startswith("_"):
            continue
        city = json.loads(path.read_text(encoding="utf-8"))
        cities[city["meta"]["city_slug"]] = city
    return cities


def list_cities() -> list[dict[str, Any]]:
    """Отдаёт список городов для enum.

    Возвращает:
        Записи вида {слаг, город, филиалов}, отсортированные по названию.
    """
    result = [
        {
            "слаг": slug,
            "город": city["meta"]["city"],
            "филиалов": len(city["branches"]["items"]),
        }
        for slug, city in _load().items()
    ]
    return sorted(result, key=lambda item: item["город"])


def list_branches(city_slug: str) -> list[dict[str, Any]]:
    """Отдаёт филиалы одного города для enum.

    Аргументы:
        city_slug: слаг города.

    Возвращает:
        Записи вида {слаг, адрес, ориентир}. Пустой список, если города нет.
    """
    city = _load().get(city_slug)
    if city is None:
        return []
    return [
        {
            "слаг": branch["id"],
            "адрес": branch["address"],
            "ориентир": branch.get("landmark"),
        }
        for branch in city["branches"]["items"]
    ]


def _fleet(city: dict[str, Any]) -> dict[str, Any]:
    """Складывает автопарк города в вид, пригодный для пересказа."""
    mkpp: list[str] = []
    akpp: list[str] = []
    year = None
    notes = []
    for item in city.get("fleet", {}).get("items", []):
        if item.get("transmission") == "МКПП":
            mkpp = item.get("models", [])
            year = year or item.get("year")
        elif item.get("transmission") == "АКПП":
            akpp = item.get("models", [])
            year = year or item.get("year")
        elif item.get("kind") == "thesis":
            notes.append(item["text"])
    return {"механика": mkpp, "автомат": akpp, "возраст парка": year, "особенности": notes}


def _categories(city: dict[str, Any]) -> list[dict[str, Any]]:
    """Собирает категории, добирая срок и стартЫ из тарифов там, где карточка неполная.

    В городах, размеченных вручную, срок обучения лежит в тарифе, а не в карточке
    категории. Здесь эти два источника сводятся в один вид.

    Аргументы:
        city: разобранный файл города.

    Возвращает:
        Список категорий для меты.
    """
    tariffs = {t.get("category"): t for t in city.get("tariffs", {}).get("items", [])}
    result = []
    for item in city.get("categories", {}).get("items", []):
        code = item.get("code")
        fallback = tariffs.get(code, {})
        result.append(
            {
                "категория": code,
                "срок обучения": item.get("duration") or fallback.get("duration"),
                "старт групп": item.get("start_frequency") or fallback.get("start_frequency"),
                "что входит": item.get("includes") or fallback.get("includes", []),
            }
        )
    return result


def get_city(city_slug: str) -> dict[str, Any] | None:
    """Отдаёт всё, что известно о городе, для информирования клиента.

    Аргументы:
        city_slug: слаг города из `list_cities`.

    Возвращает:
        Мету города или None, если такого города нет.
    """
    city = _load().get(city_slug)
    if city is None:
        return None

    branches = city["branches"]["items"]
    contacts = city.get("contacts", {})

    return {
        "город": city["meta"]["city"],
        "филиалов": sum(1 for b in branches if not b.get("is_autodrome")),
        "автодромов": sum(1 for b in branches if b.get("is_autodrome")),
        "категории": _categories(city),
        "автомобили": _fleet(city),
        "форматы теории": [
            item["text"] for item in city.get("theory_formats", {}).get("items", [])
        ],
        "документы": [
            {"что": item.get("name"), "когда": item.get("stage")}
            for item in city.get("documents", {}).get("items", [])
        ],
        "оплата": {
            "рассрочка без переплат": city.get("installment", {}).get("no_overpay"),
            "способы": city.get("installment", {}).get("methods", []),
        },
        "частые вопросы": [
            {"вопрос": item["question"], "ответ": item["answer"]}
            for item in city.get("faq", {}).get("items", [])
            if item.get("answer")
        ],
        "телефон": contacts.get("phone_federal") or contacts.get("phone_city"),
        "приём звонков": contacts.get("call_hours"),
        "мессенджеры": contacts.get("messengers", []),
    }


def get_branch(branch_slug: str) -> dict[str, Any] | None:
    """Отдаёт всё, что известно о филиале.

    Аргументы:
        branch_slug: плоский слаг филиала из `list_branches`.

    Возвращает:
        Мету филиала или None, если такого филиала нет.
    """
    for city in _load().values():
        for branch in city["branches"]["items"]:
            if branch["id"] != branch_slug:
                continue
            opened = (branch.get("hours") or "").lower().find("открыт") == -1
            return {
                "город": city["meta"]["city"],
                "адрес": branch["address"],
                "ориентир": branch.get("landmark"),
                "район": branch.get("district"),
                "метро": branch.get("metro"),
                "тип": "автодром" if branch.get("is_autodrome") else "учебный офис",
                "статус": "работает" if opened else "скоро открытие",
                "часы работы": branch.get("hours") if opened else None,
                "перерыв": branch.get("break"),
                "телефон": city.get("contacts", {}).get("phone_federal"),
                "примечание": branch.get("note"),
            }
    return None
