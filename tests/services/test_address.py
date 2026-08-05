"""Тесты нормализации адреса перед геокодированием."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.services.directory_service.address import (
    extract_own_city,
    has_own_city,
    normalize_for_geocoder,
)

#: Набор примеров для проверки формы результата.
_EXAMPLES = (
    "ул. Алексеева, 46, 2 этаж пом. 477",
    "ул. Полтавская, д. 38, стр. 4",
    "Ленинский просп., 128, корп. 2, эт. 2",
    "пр-кт им. Газеты Красноярский Рабочий, 42",
    "ул. Правды, 17, 5 этаж, офис 501",
    "ул. Гайдара 2/1, 2 этаж",
    "ул, Славы, д. 12",
    "ул. Шумяцкого, 2Е",
)


def test_cuts_entire_tail_after_first_refinement() -> None:
    """Хвост от первого уточнения срезается целиком, без остатка номера."""
    assert normalize_for_geocoder("ул. Алексеева, 46, 2 этаж пом. 477") == ("ул. Алексеева, 46")


def test_strips_structure() -> None:
    """Строение срезается — дом без него находится чаще."""
    assert normalize_for_geocoder("ул. Полтавская, д. 38, стр. 4") == ("ул. Полтавская, д. 38")


def test_keeps_structure_when_strip_building_false() -> None:
    """При strip_building=False строение и корпус сохраняются."""
    assert (
        normalize_for_geocoder("ул. Полтавская, д. 38, стр. 4", strip_building=False)
        == "ул. Полтавская, д. 38, стр. 4"
    )
    assert (
        normalize_for_geocoder("Ленинский просп., 128, корп. 2, эт. 2", strip_building=False)
        == "Ленинский проспект, 128, корп. 2"
    )


def test_strips_floor_office_even_without_strip_building() -> None:
    """Этаж и офис срезаются и при strip_building=False."""
    assert (
        normalize_for_geocoder("ул. Правды, 17, 5 этаж, офис 501", strip_building=False)
        == "ул. Правды, 17"
    )


def test_expands_prospekt_and_strips_corpus() -> None:
    """«просп.» раскрывается, корпус и этаж срезаются."""
    assert normalize_for_geocoder("Ленинский просп., 128, корп. 2, эт. 2") == (
        "Ленинский проспект, 128"
    )


def test_expands_pr_kt_im() -> None:
    """«пр-кт им.» раскрывается в «проспект» без «им.»."""
    assert normalize_for_geocoder("пр-кт им. Газеты Красноярский Рабочий, 42") == (
        "проспект Газеты Красноярский Рабочий, 42"
    )


def test_strips_floor_and_office() -> None:
    """Этаж и офис срезаются."""
    assert normalize_for_geocoder("ул. Правды, 17, 5 этаж, офис 501") == ("ул. Правды, 17")


def test_keeps_fraction_house_number() -> None:
    """Дробь в номере дома сохраняется."""
    assert normalize_for_geocoder("ул. Гайдара 2/1, 2 этаж") == "ул. Гайдара 2/1"


def test_comma_after_abbreviation_becomes_dot() -> None:
    """Запятая после сокращения превращается в точку."""
    assert normalize_for_geocoder("ул, Славы, д. 12") == "ул. Славы, д. 12"


def test_no_dangling_punctuation_or_double_spaces() -> None:
    """В результатах нет висячих запятых, точек и двойных пробелов."""
    for raw in _EXAMPLES:
        cleaned = normalize_for_geocoder(raw)
        assert cleaned == cleaned.strip(" ,.;")
        assert "  " not in cleaned
        assert not cleaned.endswith(",")
        assert not cleaned.endswith(".")


def test_clean_address_unchanged() -> None:
    """Адрес без уточнений не меняется."""
    assert normalize_for_geocoder("ул. Шумяцкого, 2Е") == "ул. Шумяцкого, 2Е"


def test_only_refinement_returns_original() -> None:
    """Адрес из одного уточнения возвращается как есть, а не пустым."""
    assert normalize_for_geocoder("5 этаж") == "5 этаж"
    assert normalize_for_geocoder("офис 501") == "офис 501"


def test_strips_shopping_center_at_end() -> None:
    """Торговый центр в конце адреса срезается вместе с названием."""
    assert normalize_for_geocoder("ул. Родионова 165 к13, ТЦ «Ганza»") == ("ул. Родионова 165 к13")
    assert normalize_for_geocoder("ул. Лежневская, 117, ТРЦ «Шоколад», эт. 4, пом. 410") == (
        "ул. Лежневская, 117"
    )
    assert normalize_for_geocoder('ул. Ф. Энгельса, д. 64А, МФК "Атмосфера", этаж 5') == (
        "ул. Ф. Энгельса, д. 64А"
    )
    assert normalize_for_geocoder('ул. Новоселов, д. 21А, БЦ "Черезово"') == (
        "ул. Новоселов, д. 21А"
    )
    assert normalize_for_geocoder("Чередовая 10-я, 17/2, ТК Сахалин, 2 этаж") == (
        "Чередовая 10-я, 17/2"
    )
    assert normalize_for_geocoder("ул. Белинского 26 тк «Средной»") == ("ул. Белинского 26")


def test_strips_shopping_center_at_start() -> None:
    """ТЦ в начале до первой запятой срезается, улица с домом остаётся."""
    assert normalize_for_geocoder("ТЦ Никольский, пр-кт. Ленина, 57А") == ("проспект. Ленина, 57А")
    assert normalize_for_geocoder("ТК Метромолл, ул. 70 лет Октября 26, 4 этаж, офис 411") == (
        "ул. 70 лет Октября 26"
    )


def test_strips_tc_titul_with_parens() -> None:
    """ТЦ в начале и скобки с офисом срезаются вместе."""
    assert normalize_for_geocoder("ТЦ Титул, улица Балтийская, 7а (офис 301, 3 этаж)") == (
        "улица Балтийская, 7а"
    )


def test_strips_any_parentheses() -> None:
    """Любое содержимое круглых скобок срезается."""
    assert normalize_for_geocoder("ул. Крупской д. 30 (вход с улицы)") == ("ул. Крупской д. 30")
    assert normalize_for_geocoder("ул. Обручева, д. 9Л (левый берег) (В категория)") == (
        "ул. Обручева, д. 9Л"
    )
    assert normalize_for_geocoder("Учебная, 38 (отдельный вход)") == "Учебная, 38"


def test_keeps_corpus_when_stripping_parens() -> None:
    """При strip_building=False корпус сохраняется, скобки срезаны."""
    assert (
        normalize_for_geocoder(
            "ул. Грязнова, д. 57 к 19 (Парковка возле автомойки)",
            strip_building=False,
        )
        == "ул. Грязнова, д. 57 к 19"
    )


def test_strips_household_and_queue() -> None:
    """Бытовые уточнения и очередь срезаются от вхождения до конца."""
    assert normalize_for_geocoder("ул. Адмирала Горшкова, 8, домофон 27") == (
        "ул. Адмирала Горшкова, 8"
    )
    assert normalize_for_geocoder("ул. Комарова 8, вход с улицы (Черниковка)") == ("ул. Комарова 8")
    assert normalize_for_geocoder("ул. Московская 70, 2-ая очередь, 2 этаж, кабинет 27") == (
        "ул. Московская 70"
    )
    assert normalize_for_geocoder("ул. Московская 70, 2-я очередь") == ("ул. Московская 70")


def test_all_directory_addresses_normalize_cleanly() -> None:
    """После нормализации ни один адрес справочника не пустой и не корявый."""
    data_dir: Path = settings.directory_data_dir
    count = 0
    for path in sorted(data_dir.glob("*.json")):
        city = json.loads(path.read_text(encoding="utf-8"))
        for branch in city["branches"]["items"]:
            count += 1
            address = branch.get("address") or ""
            cleaned = normalize_for_geocoder(address)
            assert cleaned, f"{path.name}: {branch.get('id')} стал пустым"
            assert not cleaned.endswith(","), f"{path.name}: {cleaned!r}"
            assert not cleaned.endswith("."), f"{path.name}: {cleaned!r}"
            assert "  " not in cleaned, f"{path.name}: {cleaned!r}"
    assert count == 222


def test_extract_own_city_forms() -> None:
    """extract_own_city возвращает название для всех перечисленных форм."""
    assert extract_own_city("г Артем, Площадь Ленина, 17") == "Артем"
    assert extract_own_city("г. Артем, Площадь Ленина, 17") == "Артем"
    assert extract_own_city("г.Артем, Площадь Ленина, 17") == "Артем"
    assert extract_own_city("город Всеволожск, Всеволожский проспект, 61") == "Всеволожск"
    assert extract_own_city("г. Нижний Новгород, ул. Ленина, 1") == "Нижний Новгород"
    assert extract_own_city("Р.П. Оконешниково, ул. Калинина 25") == "Оконешниково"
    assert extract_own_city("Р.П. Кормиловка, ул. Кирова 45/1") == "Кормиловка"
    assert extract_own_city("рп Кормиловка, ул. Кирова 45/1") == "Кормиловка"
    assert extract_own_city("Посёлок Ростовка, 21") == "Ростовка"
    assert extract_own_city("поселок Ростовка, 21") == "Ростовка"
    assert extract_own_city("пос. Ростовка, 21") == "Ростовка"
    assert extract_own_city("Село Поляны, ул. Терёхина, 14") == "Поляны"
    assert extract_own_city("с. Поляны, ул. Терёхина, 14") == "Поляны"
    assert extract_own_city("пгт Мурино, ул. Ленина, 1") == "Мурино"
    assert extract_own_city("д. Иваново, ул. Ленина, 1") == "Иваново"
    assert extract_own_city("деревня Иваново, ул. Ленина, 1") == "Иваново"


def test_extract_own_city_none_for_ordinary_and_house() -> None:
    """Обычный адрес и «д. 12» (дом) не считаются населённым пунктом."""
    assert extract_own_city("ул. Славы, д. 12") is None
    assert extract_own_city("улица Городская, 5") is None
    assert extract_own_city("д. 12") is None
    assert extract_own_city("д.12, офис 1") is None
    assert extract_own_city("Нижняя Омка, Пер.Школьный 14") is None
    assert extract_own_city("") is None


def test_has_own_city_recognizes_locality_spellings() -> None:
    """Явные написания населённых пунктов и составные имена распознаются."""
    assert has_own_city("г Артем, Площадь Ленина, 17", "Владивосток") is True
    assert has_own_city("г. Артем, Площадь Ленина, 17", "Владивосток") is True
    assert has_own_city("г.Артем, Площадь Ленина, 17", "Владивосток") is True
    assert has_own_city("город Всеволожск, Всеволожский проспект, 61", "Санкт-Петербург") is True
    assert has_own_city("г. Нижний Новгород, ул. Ленина, 1", "Казань") is True
    assert has_own_city("г. Старый Оскол, ул. Ленина, 1", "Белгород") is True
    assert has_own_city("г. Мурино, Привокзальная площадь, 1", "Санкт-Петербург") is True
    assert has_own_city("Красноярск, ул. Славы, 12", "Красноярск") is True
    assert has_own_city("Р.П. Оконешниково, ул. Калинина 25", "Омск") is True
    assert has_own_city("Посёлок Ростовка, 21", "Омск") is True
    assert has_own_city("Село Поляны, ул. Терёхина, 14", "Рязань") is True


def test_has_own_city_false_on_ordinary_and_street_name() -> None:
    """Обычный адрес и «улица Городская» не считаются своим городом."""
    assert has_own_city("ул. Славы, д. 12", "Красноярск") is False
    assert has_own_city("улица Городская, 5", "Красноярск") is False
    assert has_own_city("ул. Городская, 5", "Москва") is False
    assert has_own_city("", "Красноярск") is False
    assert has_own_city("Нижняя Омка, Пер.Школьный 14", "Омск") is False


def test_same_city_keeps_geocoder_restriction() -> None:
    """Совпадение населённого пункта с городом файла не снимает ограничение."""
    own = extract_own_city("г. Томск, ул. Ференца Мюнниха, 42 а")
    assert own == "Томск"
    city_title = "Томск"
    query_city = None if own is not None and own.casefold() != city_title.casefold() else city_title
    assert query_city == "Томск"

    own_other = extract_own_city("г. Мурино, Привокзальная площадь, 1")
    assert own_other == "Мурино"
    city_spb = "Санкт-Петербург"
    query_city_spb = (
        None if own_other is not None and own_other.casefold() != city_spb.casefold() else city_spb
    )
    assert query_city_spb is None
