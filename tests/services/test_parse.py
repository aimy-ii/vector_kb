"""Офлайн-тесты разбора: без сети, на зафиксированном куске реального текста."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.parsing_service.parse import (
    build,
    find_conflicts,
    parse_branches,
    parse_company,
    parse_contacts,
    parse_faq,
    parse_price_increase,
    parse_prices,
    parse_promos,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "city_sample.txt"


@pytest.fixture(scope="module")
def text() -> str:
    """Текст страницы из фикстуры."""
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lines(text: str) -> list[str]:
    """Тот же текст построчно."""
    return text.split("\n")


def test_branches_count(lines: list[str]) -> None:
    """Найдены все четыре адреса, включая автодром и «Скоро открытие»."""
    assert len(parse_branches(lines)) == 4


def test_branch_hours_and_break(lines: list[str]) -> None:
    """Часы и перерыв разобраны, когда подписи идут в обычном порядке."""
    first = parse_branches(lines)[0]
    assert first["address"] == "ул. Техническая, д. 32, 4 этаж, оф 51"
    assert first["hours"] == "ПН-ПТ 10:00-19:00"
    assert first["break"] == "14:00-15:00"
    assert first["is_autodrome"] is False


def test_branch_break_before_its_label(lines: list[str]) -> None:
    """Перерыв разобран и когда значение напечатано до подписи «Перерыв:»."""
    korzuna = next(b for b in parse_branches(lines) if "Корзуна" in b["address"])
    assert korzuna["hours"] == "ПН-ВС 10:00-20:00"
    assert korzuna["break"] == "14:00-15:00"


def test_branch_autodrome_flag(lines: list[str]) -> None:
    """Адрес под заголовком «Автодромы» помечен как автодром и остался без часов."""
    autodrome = next(b for b in parse_branches(lines) if "Норильская" in b["address"])
    assert autodrome["is_autodrome"] is True
    assert autodrome["hours"] is None


def test_branch_soon_opening(lines: list[str]) -> None:
    """«Скоро открытие» попадает в часы работы, а не теряется."""
    soon = next(b for b in parse_branches(lines) if "Васильевского" in b["address"])
    assert soon["hours"] == "Скоро открытие"
    assert soon["break"] is None


def test_prices(text: str) -> None:
    """Сумма с пробелом-разделителем разобрана и помечена как «от»."""
    prices = parse_prices(text)
    assert prices[0]["price"] == 24950
    assert prices[0]["price_is_from"] is True
    assert "теория + вождение" in prices[0]["context"]


def test_price_increase_date(text: str) -> None:
    """Дата повышения приведена к ГГГГ-ММ-ДД, причина сохранена дословно."""
    increase = parse_price_increase(text)
    assert increase["from_date"] == "2026-08-01"
    assert "горюче-смазочных" in increase["reason"]


def test_company_stats(text: str) -> None:
    """Витринные показатели разобраны числами."""
    company = parse_company(text)
    assert company["graduates"] == 200000
    assert company["years"] == 10
    assert company["first_try_pass_rate"] == 85
    assert company["cities"] == 35


def test_faq_pairs(lines: list[str]) -> None:
    """Все семь вопросов на месте, ответы подтянуты."""
    faq = parse_faq(lines)
    assert len(faq) == 7
    assert all(item["answer"] for item in faq)
    assert faq[0]["answer"].startswith("Стоимость обучения по договору окончательная")


def test_faq_answer_missing_stays_none() -> None:
    """Если тела аккордеона нет, ответ остаётся пустым, а не берётся из соседнего вопроса."""
    faq = parse_faq(["Как происходит оплата?", "Могу ли я изучать теорию дистанционно?"])
    assert faq[1]["answer"] is None


def test_promos_found(text: str) -> None:
    """Известные акции опознаны по маркерам, выгода проставлена."""
    promos = {p["id"]: p for p in parse_promos(text)}
    assert "promo_tax_deduction" in promos
    assert promos["promo_student"]["benefit"] == "1000 рублей"


def test_contacts(text: str) -> None:
    """Телефоны, ИНН, ОГРН и юрлицо вытащены из блока реквизитов."""
    contacts = parse_contacts(text, [("Лицензия", "https://disk.yandex.ru/i/abc")])
    assert contacts["phone_federal"] == "8 (800) 511-95-02"
    assert contacts["phone_city"] == "+7 (812) 338-1000"
    assert contacts["call_hours"] == "С 7:30 до 23:00"
    assert contacts["inn"] == "6663001440"
    assert contacts["ogrn"] == "1036604783874"
    assert contacts["legal_entity"] == "ООО «ВИЛЛА»"
    assert contacts["license"] == "https://disk.yandex.ru/i/abc"


def test_conflicts_installment_and_phones(text: str) -> None:
    """Два разных срока рассрочки и два телефона попали в расхождения."""
    ids = {c["id"] for c in find_conflicts(text)}
    assert "conflict_installment_term" in ids
    assert "conflict_phone" in ids


def test_build_shape(text: str) -> None:
    """Итоговый документ содержит все разделы схемы и список на проверку."""
    document = build("test", "Тестоград", "https://example.org/test", text, [], "2026-07-22")
    for section in (
        "meta",
        "branches",
        "tariffs",
        "promos",
        "price_increase",
        "fleet",
        "theory_formats",
        "installment",
        "categories",
        "faq",
        "documents",
        "company",
        "contacts",
        "groups",
        "conflicts",
    ):
        assert section in document
    assert document["meta"]["city_slug"] == "test"
    assert document["branches"]["_source"] == "https://example.org/test"
    assert document["installment"]["no_overpay"] is True
    assert document["_review"]
