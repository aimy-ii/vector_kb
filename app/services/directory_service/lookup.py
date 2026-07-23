"""Публичный API справочника для агента.

Города и филиалы адресуются плоскими слагами. Списки отдаются модели как enum,
поэтому пришедший обратно ключ валиден по построению.

Мета без технических полей и без цен: то, что возвращают `get_city` и `get_branch`,
модель пересказывает клиенту своими словами. Число с сайта занижено примерно вдвое
против реальной стоимости, поэтому вслух оно не идёт.
"""

from __future__ import annotations

from typing import Any

from app.services.directory_service.store import directory_store


def _cities() -> dict[str, dict[str, Any]]:
    """Возвращает города из памяти; при пустом кэше подгружает с диска."""
    if not directory_store.cities:
        directory_store.load()
    return directory_store.cities


def _has_price_leak(value: Any) -> bool:
    """Проверяет, есть ли в значении слово «цена» или символ ₽."""
    if value is None:
        return False
    text = str(value).lower()
    return "цена" in text or "₽" in str(value)


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
        for slug, city in _cities().items()
    ]
    return sorted(result, key=lambda item: item["город"])


def list_branches(city_slug: str) -> list[dict[str, Any]]:
    """Отдаёт филиалы одного города для enum.

    Аргументы:
        city_slug: слаг города.

    Возвращает:
        Записи вида {слаг, адрес, ориентир}. Пустой список, если города нет.
    """
    city = _cities().get(city_slug)
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


def city_enum() -> list[str]:
    """Отдаёт слаги городов для enum инструмента модели."""
    return [item["слаг"] for item in list_cities()]


def branch_enum(city_slug: str) -> list[str]:
    """Отдаёт слаги филиалов города для enum инструмента модели.

    Аргументы:
        city_slug: слаг города.
    """
    return [item["слаг"] for item in list_branches(city_slug)]


def _fleet(city: dict[str, Any]) -> dict[str, Any]:
    """Складывает автопарк города в вид, пригодный для пересказа."""
    mkpp: list[str] = []
    akpp: list[str] = []
    year: str | None = None
    notes: list[str] = []
    for item in city.get("fleet", {}).get("items", []):
        if item.get("transmission") == "МКПП":
            mkpp = item.get("models", [])
            year = year or item.get("year")
        elif item.get("transmission") == "АКПП":
            akpp = item.get("models", [])
            year = year or item.get("year")
        elif item.get("kind") == "thesis":
            text = item.get("text")
            if text and not _has_price_leak(text):
                notes.append(text)
    return {"механика": mkpp, "автомат": akpp, "возраст парка": year, "особенности": notes}


def _categories(city: dict[str, Any]) -> list[dict[str, Any]]:
    """Собирает категории без цен и служебных полей."""
    result: list[dict[str, Any]] = []
    for item in city.get("categories", {}).get("items", []):
        result.append(
            {
                "категория": item.get("code"),
                "срок обучения": item.get("duration"),
                "старт групп": item.get("start_frequency"),
                "что входит": item.get("includes") or [],
            }
        )
    return result


def get_city(city_slug: str) -> dict[str, Any] | None:
    """Отдаёт всё, что известно о городе, для информирования клиента.

    Аргументы:
        city_slug: слаг города из `list_cities` / `city_enum`.

    Возвращает:
        Мету города или None, если такого города нет.
    """
    city = _cities().get(city_slug)
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
            item["text"]
            for item in city.get("theory_formats", {}).get("items", [])
            if item.get("text") and not _has_price_leak(item["text"])
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
            if item.get("answer") and not _has_price_leak(item["answer"])
        ],
        "телефон": contacts.get("phone_federal") or contacts.get("phone_city"),
        "приём звонков": contacts.get("call_hours"),
        "мессенджеры": contacts.get("messengers", []),
    }


def get_branch(branch_slug: str) -> dict[str, Any] | None:
    """Отдаёт всё, что известно о филиале.

    Аргументы:
        branch_slug: плоский слаг филиала из `list_branches` / `branch_enum`.

    Возвращает:
        Мету филиала или None, если такого филиала нет.
    """
    for city in _cities().values():
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
