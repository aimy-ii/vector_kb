"""Список городов сети «Вектор» и их адресов на сайте.

Список снят вручную с переключателя городов на avtoschool-vektor.ru 22.07.2026.
Три города живут на отдельных доменах — у них другая вёрстка, парсер их пропускает,
если не передан флаг --external.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = "https://avtoschool-vektor.ru"


@dataclass(frozen=True)
class City:
    """Один город сети.

    Аргументы:
        slug: короткий идентификатор латиницей, он же имя выходного файла.
        name: название города так, как оно написано на сайте.
        url: адрес городской страницы.
        external: True, если город на отдельном домене (вёрстка другая, парсер не гарантирован).
        done: True, если город уже собран вручную и его можно пропустить.
    """

    slug: str
    name: str
    url: str
    external: bool = False
    done: bool = False


CITIES: tuple[City, ...] = (
    City("sankt-peterburg", "Санкт-Петербург", f"{BASE}/sankt-peterburg", done=True),
    City("ekaterinburg", "Екатеринбург", f"{BASE}/ekaterinburg", done=True),
    City("perm", "Пермь", f"{BASE}/perm", done=True),
    City("omsk", "Омск", f"{BASE}/"),
    City("novosib", "Новосибирск", f"{BASE}/novosib"),
    City("krasnoyarsk", "Красноярск", f"{BASE}/krasnoyarsk"),
    City("kazan", "Казань", f"{BASE}/kazan"),
    City("nizhniy-novgorod", "Нижний Новгород", f"{BASE}/nizhniy-novgorod"),
    City("tagil", "Нижний Тагил", f"{BASE}/tagil"),
    City("novokuznetsk", "Новокузнецк", f"{BASE}/novokuznetsk"),
    City("nazyvayevsk", "Называевск", f"{BASE}/nazyvayevsk"),
    City("magnitogorsk", "Магнитогорск", f"{BASE}/magnitogorsk"),
    City("ryazan", "Рязань", f"{BASE}/ryazan"),
    City("dagomyc", "Дагомыс", f"{BASE}/dagomyc"),
    City("zheleznogorsk", "Железногорск", f"{BASE}/zheleznogorsk"),
    City("eletz", "Елец", f"{BASE}/eletz"),
    City("yaroslavl", "Ярославль", f"{BASE}/yaroslavl"),
    City("sochi", "Сочи", f"{BASE}/sochi"),
    City("sterlitamak", "Стерлитамак", f"{BASE}/sterlitamak"),
    City("ufa", "Уфа", f"{BASE}/ufa"),
    City("penza", "Пенза", f"{BASE}/penza"),
    City("ishim", "Ишим", f"{BASE}/ishim"),
    City("irkutsk", "Иркутск", f"{BASE}/irkutsk"),
    City("ivanovo", "Иваново", f"{BASE}/ivanovo"),
    City("izhevsk", "Ижевск", f"{BASE}/izhevsk"),
    City("vladivostok", "Владивосток", f"{BASE}/vladivostok"),
    City("voronezh", "Воронеж", f"{BASE}/voronezh"),
    City("barnaul", "Барнаул", f"{BASE}/barnaul"),
    City("abakan", "Абакан", f"{BASE}/abakan"),
    City("adler", "Адлер", f"{BASE}/adler"),
    City("artem", "Артём", f"{BASE}/artem"),
    City("achinsk", "Ачинск", f"{BASE}/achinsk"),
    City("tomsk", "Томск", f"{BASE}/tomsk"),
    City("tyumen", "Тюмень", f"{BASE}/72"),
    City("tara", "Тара", f"{BASE}/tara"),
    City("kansk", "Канск", f"{BASE}/kansk"),
    City("kemerovo", "Кемерово", f"{BASE}/kemerovo"),
    City("kopeysk", "Копейск", f"{BASE}/kopeysk"),
    City("kyrgan", "Курган", f"{BASE}/kyrgan"),
    City("kalachinsk", "Калачинск", f"{BASE}/kalachinsk"),
    City("kormilovka", "Кормиловка", f"{BASE}/kormilovka"),
    City("lipetsk", "Липецк", "https://vektor48.ru/", external=True),
    City("chelyabinsk", "Челябинск", "https://vektor174.ru/", external=True),
    City(
        "kaliningrad",
        "Калининград",
        "https://xn--80aaicjcfbdgcv0abfhcfr7n.xn--p1ai/",
        external=True,
    ),
)
"""Все 44 города переключателя. Порядок: сначала уже собранные, дальше по приоритету."""


def select(
    *, include_done: bool = False, include_external: bool = False, only: list[str] | None = None
) -> list[City]:
    """Отбирает города для обхода.

    Аргументы:
        include_done: включать ли города, уже собранные вручную.
        include_external: включать ли города на чужих доменах.
        only: список слагов; если задан, остальные фильтры игнорируются.

    Возвращает:
        Список городов в порядке из CITIES.
    """
    if only:
        wanted = set(only)
        return [c for c in CITIES if c.slug in wanted]
    result = []
    for city in CITIES:
        if city.done and not include_done:
            continue
        if city.external and not include_external:
            continue
        result.append(city)
    return result
