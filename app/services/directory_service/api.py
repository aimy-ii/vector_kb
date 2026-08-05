"""Сервисный слой справочника для API: сборка английских схем из меты."""

from __future__ import annotations

from typing import Any

from app.constants.directory import PRICE_DISCLAIMER, PRICE_UNKNOWN
from app.schemas.common import HealthResponse, ReloadResponse
from app.schemas.directory import (
    BranchDetail,
    BranchNearby,
    BranchShort,
    CategoryInfo,
    CityDetail,
    CityResolve,
    CityShort,
    DocumentInfo,
    FaqItem,
    GeocodeResult,
    PaymentInfo,
    PriceInfo,
    VehiclesInfo,
)
from app.services.directory_service import (
    city_name,
    directory_store,
    get_branch,
    get_city,
    list_branches,
    list_cities,
    nearest_branches,
    resolve_city,
)
from app.services.directory_service.geocoders import geocoder


def health() -> HealthResponse:
    """Собирает снимок живости сервиса."""
    return HealthResponse(
        status="ok",
        cities_count=directory_store.cities_count,
        branches_count=directory_store.branches_count,
        loaded_at=directory_store.loaded_at,
    )


def reload_directory() -> ReloadResponse:
    """Перечитывает файлы справочника в память."""
    directory_store.reload()
    return ReloadResponse(
        cities_count=directory_store.cities_count,
        branches_count=directory_store.branches_count,
        loaded_at=directory_store.loaded_at,
    )


def cities_short() -> list[CityShort]:
    """Список городов для API."""
    return [
        CityShort(slug=item["слаг"], name=item["город"], branches_count=item["филиалов"])
        for item in list_cities()
    ]


def cities_enum() -> list[str]:
    """Плоский список слагов городов."""
    return [item["слаг"] for item in list_cities()]


def build_price_info(tariffs: dict[str, Any] | None) -> PriceInfo:
    """Собирает витринную цену из раздела `tariffs`.

    Берёт первый тариф с непустой суммой. Число с сайта — маркетинговое «от»,
    поэтому `reliable` всегда False, а `note` — обязательная оговорка для бота.
    Если суммы нет, `amount` остаётся None, а `note` сообщает, что цену назовёт
    менеджер.

    Args:
        tariffs: раздел `tariffs` из JSON города или None.

    Returns:
        PriceInfo с суммой (или без неё) и оговоркой.
    """
    items: list[Any] = []
    if isinstance(tariffs, dict):
        raw_items = tariffs.get("items", [])
        if isinstance(raw_items, list):
            items = raw_items

    for item in items:
        if not isinstance(item, dict):
            continue
        amount = item.get("price")
        if amount is None:
            continue
        is_from = item.get("price_is_from")
        return PriceInfo(
            amount=int(amount),
            is_from=True if is_from is None else bool(is_from),
            package=item.get("name"),
            reliable=False,
            note=PRICE_DISCLAIMER,
        )

    return PriceInfo(
        amount=None,
        is_from=True,
        package=None,
        reliable=False,
        note=PRICE_UNKNOWN,
    )


def city_detail(city_slug: str) -> CityDetail | None:
    """Полная мета города в схеме API."""
    meta = get_city(city_slug)
    if meta is None:
        return None
    if not directory_store.cities:
        directory_store.load()
    raw_city = directory_store.cities.get(city_slug, {})
    payment = meta["оплата"]
    vehicles = meta["автомобили"]
    return CityDetail(
        slug=city_slug,
        name=meta["город"],
        branches_count=meta["филиалов"],
        autodromes_count=meta["автодромов"],
        categories=[
            CategoryInfo(
                code=item["категория"],
                duration=item["срок обучения"],
                start_frequency=item["старт групп"],
                includes=item["что входит"] or [],
            )
            for item in meta["категории"]
        ],
        vehicles=VehiclesInfo(
            manual=vehicles["механика"],
            automatic=vehicles["автомат"],
            fleet_age=vehicles["возраст парка"],
            notes=vehicles["особенности"],
        ),
        theory_formats=meta["форматы теории"],
        documents=[
            DocumentInfo(name=item["что"], stage=item["когда"]) for item in meta["документы"]
        ],
        payment=PaymentInfo(
            installment_no_overpay=payment.get("рассрочка без переплат"),
            methods=payment.get("способы") or [],
        ),
        faq=[
            FaqItem(question=item["вопрос"], answer=item["ответ"])
            for item in meta["частые вопросы"]
        ],
        phone=meta["телефон"],
        call_hours=meta["приём звонков"],
        messengers=meta["мессенджеры"] or [],
        price=build_price_info(raw_city.get("tariffs")),
    )


def branches_short(city_slug: str) -> list[BranchShort] | None:
    """Филиалы города; None, если города нет."""
    if get_city(city_slug) is None:
        return None
    return [
        BranchShort(slug=item["слаг"], address=item["адрес"], landmark=item["ориентир"])
        for item in list_branches(city_slug)
    ]


def branches_enum(city_slug: str) -> list[str] | None:
    """Слаги филиалов города; None, если города нет."""
    if get_city(city_slug) is None:
        return None
    return [item["слаг"] for item in list_branches(city_slug)]


def branch_detail(branch_slug: str) -> BranchDetail | None:
    """Полная мета филиала в схеме API."""
    meta = get_branch(branch_slug)
    if meta is None:
        return None
    return BranchDetail(
        slug=branch_slug,
        city=meta["город"],
        address=meta["адрес"],
        landmark=meta["ориентир"],
        district=meta["район"],
        metro=list(meta["метро"] or []) if not isinstance(meta["метро"], str) else [meta["метро"]],
        place_type=meta["тип"],
        status=meta["статус"],
        working_hours=meta["часы работы"],
        break_time=meta["перерыв"],
        phone=meta["телефон"],
        note=meta["примечание"],
    )


def resolve_city_text(text: str) -> CityResolve:
    """Разбор разговорного названия; slug=null — города нет в сети."""
    return CityResolve(text=text, slug=resolve_city(text))


def nearest_branches_short(
    lat: float,
    lon: float,
    limit: int,
    radius_km: float,
    city_slug: str | None = None,
) -> list[BranchNearby]:
    """Ближайшие филиалы к точке в схеме API."""
    return [
        BranchNearby(
            slug=item["слаг"],
            city=item["город"],
            address=item["адрес"],
            landmark=item["ориентир"],
            distance_km=item["расстояние"],
        )
        for item in nearest_branches(
            lat=lat, lon=lon, limit=limit, radius_km=radius_km, city_slug=city_slug
        )
    ]


async def geocode_text(text: str, city_slug: str | None = None) -> GeocodeResult:
    """
    Переводит произнесённое место в координаты.

    Если город известен, его название дописывается к месту в порядке выбранного
    провайдера и дополнительно передаётся отдельным аргументом (для ограничения
    поиска у Подсказок DaData). Название берётся из справочника, а не из реплики
    клиента. Неизвестный слаг ошибкой не считается — запрос уходит как есть.

    Аргументы:
        text: место словами — район, улица, ориентир.
        city_slug: слаг города, если он уже выяснен в разговоре.

    Возвращает:
        GeocodeResult; found=False — место не распознано. Поле `text` остаётся
        исходным, без подставленного города.
    """
    name = city_name(city_slug) if city_slug else None
    query = geocoder.build_query(text, name)
    point = await geocoder.geocode(query, city=name)
    if point is None:
        return GeocodeResult(text=text, lat=None, lon=None, found=False)
    return GeocodeResult(text=text, lat=point[0], lon=point[1], found=True)
