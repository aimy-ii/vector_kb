"""Офлайн-тесты поисковика: без сети, на реальных файлах справочника."""

from __future__ import annotations

import directory
import pytest

import lookup


@pytest.fixture(autouse=True)
def _clear_cache():
    """Сбрасывает кэш загрузки перед каждым тестом."""
    directory._load.cache_clear()


@pytest.fixture
def city_slug() -> str:
    """Слаг первого города."""
    return directory.list_cities()[0]["слаг"]


@pytest.fixture
def branch_slug(city_slug: str) -> str:
    """Слаг первого филиала первого города."""
    return directory.list_branches(city_slug)[0]["слаг"]


# --- resolve -------------------------------------------------------------------


def test_resolve_city(city_slug: str):
    """Слаг города опознаётся как город."""
    kind, meta = lookup.resolve(city_slug)
    assert kind == "город"
    assert meta["город"]


def test_resolve_branch(branch_slug: str):
    """Слаг филиала опознаётся как филиал."""
    kind, meta = lookup.resolve(branch_slug)
    assert kind == "филиал"
    assert meta["адрес"]


def test_resolve_strips_spaces(city_slug: str):
    """Лишние пробелы при вставке слага не мешают."""
    assert lookup.resolve(f"  {city_slug}  ")[0] == "город"


def test_resolve_unknown():
    """Неизвестный слаг даёт None, а не исключение."""
    assert lookup.resolve("нет-такого-слага") is None


def test_resolve_empty():
    """Пустой ввод даёт None."""
    assert lookup.resolve("") is None
    assert lookup.resolve("   ") is None


def test_city_and_branch_namespaces_do_not_collide():
    """Слаг города никогда не совпадает со слагом филиала."""
    cities = {c["слаг"] for c in directory.list_cities()}
    branches = {b["слаг"] for c in cities for b in directory.list_branches(c)}
    assert not (cities & branches)


# --- suggest -------------------------------------------------------------------


def test_suggest_finds_by_prefix(branch_slug: str):
    """Обрезанный слаг подсказывает полный."""
    assert branch_slug in lookup.suggest(branch_slug[:-4])


def test_suggest_finds_by_fragment(city_slug: str):
    """Поиск по куску в середине тоже работает."""
    assert lookup.suggest(city_slug[1:4])


def test_suggest_respects_limit():
    """Подсказок не больше запрошенного числа."""
    assert len(lookup.suggest("a", limit=3)) <= 3


def test_suggest_empty_input():
    """На пустой ввод подсказок нет."""
    assert lookup.suggest("") == []


def test_suggest_nothing_similar():
    """На бессмыслицу подсказок нет."""
    assert lookup.suggest("zzzzzzzz") == []


# --- рендер --------------------------------------------------------------------


def test_render_city_has_name_and_phone(city_slug: str):
    """В выводе города есть название и телефон."""
    text = lookup.render_city(directory.get_city(city_slug))
    assert directory.get_city(city_slug)["город"] in text
    assert "телефон" in text


def test_render_city_has_no_price(city_slug: str):
    """Цена в вывод города не просачивается."""
    text = lookup.render_city(directory.get_city(city_slug)).lower()
    assert "цена" not in text
    assert "₽" not in text
    assert "руб" not in text


def test_render_branch_has_address(branch_slug: str):
    """В выводе филиала есть адрес и тип."""
    meta = directory.get_branch(branch_slug)
    text = lookup.render_branch(meta)
    assert meta["адрес"] in text
    assert "тип" in text


def test_render_skips_empty_fields(branch_slug: str):
    """Пустые поля в вывод не попадают."""
    text = lookup.render_branch(directory.get_branch(branch_slug))
    assert "None" not in text
    assert ": \n" not in text


def test_render_cities_lists_all():
    """Список городов содержит все слаги."""
    text = lookup.render_cities()
    for city in directory.list_cities():
        assert city["слаг"] in text


def test_render_branches_unknown_city():
    """Список филиалов несуществующего города даёт понятное сообщение."""
    assert "нет" in lookup.render_branches("нет-такого").lower()


# --- handle --------------------------------------------------------------------


def test_handle_city(city_slug: str):
    """Команда со слагом города печатает карточку города."""
    assert "филиалов" in lookup.handle(city_slug)


def test_handle_branch(branch_slug: str):
    """Команда со слагом филиала печатает карточку филиала."""
    assert "тип" in lookup.handle(branch_slug)


def test_handle_cities_command():
    """Команда «города» печатает список."""
    assert directory.list_cities()[0]["слаг"] in lookup.handle("города")


def test_handle_branches_command(city_slug: str):
    """Команда «филиалы <слаг>» печатает филиалы города."""
    text = lookup.handle(f"филиалы {city_slug}")
    assert directory.list_branches(city_slug)[0]["слаг"] in text


def test_handle_branches_without_argument():
    """Команда «филиалы» без слага подсказывает формат."""
    assert "слаг" in lookup.handle("филиалы").lower()


def test_handle_help():
    """Команда помощи печатает подсказку."""
    assert "город" in lookup.handle("помощь").lower()


def test_handle_empty():
    """Пустая строка не печатает ничего."""
    assert lookup.handle("   ") == ""


def test_handle_unknown_offers_suggestions(branch_slug: str):
    """На обрезанный слаг предлагаются похожие."""
    text = lookup.handle(branch_slug[:-4])
    assert "Похожие" in text
    assert branch_slug in text


def test_handle_unknown_without_suggestions():
    """На бессмыслицу отвечает, что похожих нет."""
    assert "похожих нет" in lookup.handle("zzzzzzzz").lower()


def test_handle_case_insensitive_commands():
    """Команды понимаются независимо от регистра."""
    assert lookup.handle("ГОРОДА") == lookup.handle("города")


# --- main ----------------------------------------------------------------------


def test_main_one_shot(capsys, branch_slug: str):
    """Разовый запуск с аргументом печатает карточку и возвращает 0."""
    assert lookup.main([branch_slug]) == 0
    assert directory.get_branch(branch_slug)["адрес"] in capsys.readouterr().out


def test_main_reports_missing_data(capsys, monkeypatch):
    """Если данных нет, main сообщает об этом и возвращает 1."""
    monkeypatch.setattr(directory, "list_cities", lambda: [])
    assert lookup.main(["perm"]) == 1
    assert "нет данных" in capsys.readouterr().out.lower()
