"""Сервис справочника: загрузка в память и поиск по слагу."""

from __future__ import annotations

from app.services.directory_service.aliases import resolve_city
from app.services.directory_service.lookup import (
    branch_enum,
    city_enum,
    city_name,
    get_branch,
    get_city,
    list_branches,
    list_cities,
    nearest_branches,
)
from app.services.directory_service.store import directory_store

__all__ = [
    "branch_enum",
    "city_enum",
    "city_name",
    "directory_store",
    "get_branch",
    "get_city",
    "list_branches",
    "list_cities",
    "nearest_branches",
    "resolve_city",
]
