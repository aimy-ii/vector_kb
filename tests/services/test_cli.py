"""Офлайн-тесты CLI поиска: без сети, на реальных файлах справочника."""

from __future__ import annotations

import pytest
from app import cli
from app.services.directory_service import get_branch, get_city, list_branches, list_cities
from app.services.directory_service.store import directory_store


@pytest.fixture(autouse=True)
def _reload_store() -> None:
    """Перечитывает справочник перед каждым тестом."""
    directory_store.load()


@pytest.fixture
def city_slug() -> str:
    """Слаг первого города."""
    return list_cities()[0]["слаг"]


@pytest.fixture
def branch_slug(city_slug: str) -> str:
    """Слаг первого филиала первого города."""
    return list_branches(city_slug)[0]["слаг"]


def test_resolve_city(city_slug: str) -> None:
    """Слаг города опознаётся как город."""
    kind, meta = cli.resolve(city_slug)
    assert kind == "город"
    assert meta["город"]


def test_resolve_branch(branch_slug: str) -> None:
    """Слаг филиала опознаётся как филиал."""
    kind, meta = cli.resolve(branch_slug)
    assert kind == "филиал"
    assert meta["адрес"]


def test_resolve_strips_spaces(city_slug: str) -> None:
    """Лишние пробелы при вставке слага не мешают."""
    assert cli.resolve(f"  {city_slug}  ")[0] == "город"


def test_resolve_unknown() -> None:
    """Неизвестный слаг даёт None, а не исключение."""
    assert cli.resolve("нет-такого-слага") is None


def test_resolve_empty() -> None:
    """Пустой ввод даёт None."""
    assert cli.resolve("") is None
    assert cli.resolve("   ") is None


def test_city_and_branch_namespaces_do_not_collide() -> None:
    """Слаг города никогда не совпадает со слагом филиала."""
    cities = {c["слаг"] for c in list_cities()}
    branches = {b["слаг"] for c in cities for b in list_branches(c)}
    assert not (cities & branches)


def test_suggest_finds_by_prefix(branch_slug: str) -> None:
    """Обрезанный слаг подсказывает полный."""
    assert branch_slug in cli.suggest(branch_slug[:-4])


def test_suggest_finds_by_fragment(city_slug: str) -> None:
    """Поиск по куску в середине тоже работает."""
    assert cli.suggest(city_slug[1:4])


def test_suggest_respects_limit() -> None:
    """Подсказок не больше запрошенного числа."""
    assert len(cli.suggest("a", limit=3)) <= 3


def test_suggest_empty_input() -> None:
    """На пустой ввод подсказок нет."""
    assert cli.suggest("") == []


def test_suggest_nothing_similar() -> None:
    """На бессмыслицу подсказок нет."""
    assert cli.suggest("zzzzzzzz") == []


def test_render_city_has_name_and_phone(city_slug: str) -> None:
    """В выводе города есть название и телефон."""
    text = cli.render_city(get_city(city_slug))
    assert get_city(city_slug)["город"] in text
    assert "телефон" in text


def test_render_city_has_no_price(city_slug: str) -> None:
    """Цена в вывод города не просачивается."""
    text = cli.render_city(get_city(city_slug)).lower()
    assert "цена" not in text
    assert "₽" not in text
    assert "руб" not in text


def test_render_branch_has_address(branch_slug: str) -> None:
    """В выводе филиала есть адрес и тип."""
    meta = get_branch(branch_slug)
    text = cli.render_branch(meta)
    assert meta["адрес"] in text
    assert "тип" in text


def test_render_skips_empty_fields(branch_slug: str) -> None:
    """Пустые поля в вывод не попадают."""
    text = cli.render_branch(get_branch(branch_slug))
    assert "None" not in text
    assert ": \n" not in text


def test_render_cities_lists_all() -> None:
    """Список городов содержит все слаги."""
    text = cli.render_cities()
    for city in list_cities():
        assert city["слаг"] in text


def test_render_branches_unknown_city() -> None:
    """Список филиалов несуществующего города даёт понятное сообщение."""
    assert "нет" in cli.render_branches("нет-такого").lower()


def test_handle_city(city_slug: str) -> None:
    """Команда со слагом города печатает карточку города."""
    assert "филиалов" in cli.handle(city_slug)


def test_handle_branch(branch_slug: str) -> None:
    """Команда со слагом филиала печатает карточку филиала."""
    assert "тип" in cli.handle(branch_slug)


def test_handle_cities_command() -> None:
    """Команда «города» печатает список."""
    assert list_cities()[0]["слаг"] in cli.handle("города")


def test_handle_branches_command(city_slug: str) -> None:
    """Команда «филиалы <слаг>» печатает филиалы города."""
    text = cli.handle(f"филиалы {city_slug}")
    assert list_branches(city_slug)[0]["слаг"] in text


def test_handle_branches_without_argument() -> None:
    """Команда «филиалы» без слага подсказывает формат."""
    assert "слаг" in cli.handle("филиалы").lower()


def test_handle_help() -> None:
    """Команда помощи печатает подсказку."""
    assert "город" in cli.handle("помощь").lower()


def test_handle_empty() -> None:
    """Пустая строка не печатает ничего."""
    assert cli.handle("   ") == ""


def test_handle_unknown_offers_suggestions(branch_slug: str) -> None:
    """На обрезанный слаг предлагаются похожие."""
    text = cli.handle(branch_slug[:-4])
    assert "Похожие" in text
    assert branch_slug in text


def test_handle_unknown_without_suggestions() -> None:
    """На бессмыслицу отвечает, что похожих нет."""
    assert "похожих нет" in cli.handle("zzzzzzzz").lower()


def test_handle_case_insensitive_commands() -> None:
    """Команды понимаются независимо от регистра."""
    assert cli.handle("ГОРОДА") == cli.handle("города")


def test_main_one_shot(capsys, branch_slug: str) -> None:
    """Разовый запуск с аргументом печатает карточку и возвращает 0."""
    assert cli.main([branch_slug]) == 0
    assert get_branch(branch_slug)["адрес"] in capsys.readouterr().out


def test_main_reports_missing_data(capsys, monkeypatch) -> None:
    """Если данных нет, main сообщает об этом и возвращает 1."""
    monkeypatch.setattr("app.cli.list_cities", lambda: [])
    assert cli.main(["perm"]) == 1
    assert "нет данных" in capsys.readouterr().out.lower()
