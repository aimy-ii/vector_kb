"""Эндпоинты справочника городов и филиалов."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.directory import (
    BranchDetail,
    BranchShort,
    CityDetail,
    CityResolve,
    CityShort,
)
from app.services import directory_api

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
