"""Константы справочника: типы точек, статусы, лимиты выдачи."""

from __future__ import annotations

from enum import StrEnum


class PlaceType(StrEnum):
    """Тип точки филиала."""

    OFFICE = "учебный офис"
    AUTODROME = "автодром"


class BranchStatus(StrEnum):
    """Статус филиала."""

    OPEN = "работает"
    SOON = "скоро открытие"


DEFAULT_SUGGEST_LIMIT = 8
"""Сколько похожих слагов предлагать при неверном вводе."""
