"""Пакет справочника автошколы «Вектор» для голосового бота.

Ставится отдельно от проекта сбора. Все нужные функции доступны через импорт:

    from vektor_directory import get_city, city_enum, resolve_city
"""

from __future__ import annotations

from vektor_directory.aliases import resolve_city
from vektor_directory.lookup import (
    branch_enum,
    city_enum,
    get_branch,
    get_city,
    list_branches,
    list_cities,
)

__all__ = [
    "branch_enum",
    "city_enum",
    "get_branch",
    "get_city",
    "list_branches",
    "list_cities",
    "resolve_city",
]
