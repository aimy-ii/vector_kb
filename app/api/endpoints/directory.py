"""Эндпоинты справочника городов и филиалов."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.directory import (
    BranchDetail,
    BranchNearby,
    BranchShort,
    CityDetail,
    CityResolve,
    CityShort,
    GeocodeResult,
)
from app.services.directory_service import api as directory_api

directory_router = APIRouter()


@directory_router.get(
    path="/cities",
    summary="Список городов",
    response_model=list[CityShort],
)
async def get_cities() -> list[CityShort]:
    """Возвращает слаг, название и число филиалов по каждому городу."""
    return directory_api.cities_short()


@directory_router.get(
    path="/cities/enum",
    summary="Слаги городов для enum инструмента",
    response_model=list[str],
)
async def get_cities_enum() -> list[str]:
    """Плоский список слагов городов."""
    return directory_api.cities_enum()


@directory_router.get(
    path="/cities/resolve",
    summary="Разбор разговорного названия города",
    response_model=CityResolve,
)
async def get_cities_resolve(
    text: str = Query(..., title="Текст", description="Название или разговорный вариант"),
) -> CityResolve:
    """Ищет слаг по названию; для города вне сети возвращает slug=null и 200."""
    return directory_api.resolve_city_text(text)


@directory_router.get(
    path="/cities/{city_slug}",
    summary="Полная мета города",
    response_model=CityDetail,
)
async def get_city(city_slug: str) -> CityDetail:
    """Отдаёт карточку города для пересказа клиенту."""
    detail = directory_api.city_detail(city_slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Город «{city_slug}» не найден")
    return detail


@directory_router.get(
    path="/cities/{city_slug}/branches",
    summary="Филиалы города",
    response_model=list[BranchShort],
)
async def get_city_branches(city_slug: str) -> list[BranchShort]:
    """Список филиалов: слаг, адрес, ориентир."""
    branches = directory_api.branches_short(city_slug)
    if branches is None:
        raise HTTPException(status_code=404, detail=f"Город «{city_slug}» не найден")
    return branches


@directory_router.get(
    path="/cities/{city_slug}/branches/enum",
    summary="Слаги филиалов города для enum",
    response_model=list[str],
)
async def get_city_branches_enum(city_slug: str) -> list[str]:
    """Плоский список слагов филиалов города."""
    slugs = directory_api.branches_enum(city_slug)
    if slugs is None:
        raise HTTPException(status_code=404, detail=f"Город «{city_slug}» не найден")
    return slugs


@directory_router.get(
    path="/branches/nearest",
    summary="Ближайшие филиалы к точке",
    response_model=list[BranchNearby],
)
async def get_nearest_branches(
    lat: float = Query(..., ge=-90, le=90, title="Широта"),
    lon: float = Query(..., ge=-180, le=180, title="Долгота"),
    limit: int | None = Query(default=None, ge=1, le=10, title="Сколько вернуть"),
    radius_km: float | None = Query(default=None, gt=0, le=500, title="Радиус, км"),
    city_slug: str | None = Query(default=None, title="Слаг города, если известен"),
) -> list[BranchNearby]:
    """Отдаёт ближайшие филиалы; пустой список — в радиусе никого нет."""
    return directory_api.nearest_branches_short(
        lat=lat,
        lon=lon,
        limit=limit if limit is not None else settings.nearest_limit,
        radius_km=radius_km if radius_km is not None else settings.nearest_radius_km,
        city_slug=city_slug,
    )


@directory_router.get(
    path="/geocode",
    summary="Перевод произнесённого места в координаты",
    response_model=GeocodeResult,
)
async def get_geocode(
    text: str = Query(..., min_length=2, title="Место словами"),
    city_slug: str | None = Query(default=None, title="Слаг города, если известен"),
) -> GeocodeResult:
    """Переводит фразу вида «Купчино» в координаты с учётом города."""
    return await directory_api.geocode_text(text, city_slug=city_slug)


@directory_router.get(
    path="/branches/{branch_slug}",
    summary="Полная мета филиала",
    response_model=BranchDetail,
)
async def get_branch(branch_slug: str) -> BranchDetail:
    """Отдаёт карточку филиала для пересказа клиенту."""
    detail = directory_api.branch_detail(branch_slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Филиал «{branch_slug}» не найден")
    return detail
