"""Публичный API справочника для агента.

Города и филиалы адресуются плоскими слагами. Списки отдаются модели как enum,
поэтому пришедший обратно ключ валиден по построению.

`get_city` и `get_branch` отдают мету без технических полей и без сырых тарифов:
витринная цена с оговоркой собирается отдельно в API-слое (`PriceInfo`).
В FAQ, теории и тезисах автопарка упоминания цены по-прежнему отфильтровываются,
чтобы голое маркетинговое число не ушло в пересказ без оговорки.
"""

from __future__ import annotations

from typing import Any

from app.services.directory_service.geo import distance_km, is_valid_point
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


def city_name(city_slug: str) -> str | None:
    """
    Отдаёт официальное название города по слагу.

    Аргументы:
        city_slug: слаг города.

    Возвращает:
        Название или None, если города нет в справочнике.
    """
    city = _cities().get(city_slug)
    if city is None:
        return None
    return city["meta"]["city"]


def nearest_branches(
    lat: float,
    lon: float,
    limit: int = 3,
    radius_km: float = 50.0,
    city_slug: str | None = None,
    include_autodromes: bool = False,
    include_upcoming: bool = False,
) -> list[dict[str, Any]]:
    """
    Подбирает ближайшие филиалы к заданной точке.

    По умолчанию перебирает всю сеть одним плоским списком: точек порядка
    сотен, отдельный отбор по городу ради скорости не нужен. Параметр
    `city_slug` сужает выдачу, когда город уже известен из разговора.

    Филиалы без координат в выдачу не попадают. Радиус отсекает случай, когда
    точка оказалась далеко от любой из школ, — иначе ближайший нашёлся бы
    всегда, хоть за сотни километров.

    Аргументы:
        lat: широта точки отсчёта.
        lon: долгота точки отсчёта.
        limit: сколько филиалов вернуть.
        radius_km: максимальное расстояние; дальше филиал не предлагается.
        city_slug: слаг города или None для поиска по всей сети.
        include_autodromes: включать ли автодромы вместе с учебными офисами.
        include_upcoming: включать ли точки со статусом «скоро открытие».

    Возвращает:
        Список записей с полями карточки филиала (без примечания) и
        расстоянием, отсортированный по возрастанию расстояния. Пустой
        список, если в радиусе никого нет.
    """
    found: list[dict[str, Any]] = []
    for slug, city in _cities().items():
        if city_slug is not None and slug != city_slug:
            continue
        for branch in city["branches"]["items"]:
            if not include_autodromes and branch.get("is_autodrome"):
                continue
            hours = (branch.get("hours") or "").lower()
            if not include_upcoming and "открыт" in hours:
                continue
            b_lat, b_lon = branch.get("lat"), branch.get("lon")
            if not is_valid_point(b_lat, b_lon):
                continue
            distance = distance_km(lat, lon, b_lat, b_lon)
            if distance > radius_km:
                continue
            opened = "открыт" not in hours
            found.append(
                {
                    "слаг": branch["id"],
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
                    "расстояние": round(distance, 2),
                }
            )
    found.sort(key=lambda item: item["расстояние"])
    return found[:limit]
