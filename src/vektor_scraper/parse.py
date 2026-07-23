"""Разбор плоского текста городской страницы в справочник по целевой схеме.

Подход намеренно тупой и текстовый: страницы собраны в Tilda, классы блоков от города
к городу пляшут, поэтому опираемся на подписи («Адрес:», «Время работы:», «Перерыв:»)
и на устойчивые формулировки, которые повторяются во всех городах.

Всё, что не удалось достать уверенно, кладём в `_review` внутри выходного файла:
это список полей, которые надо глазами проверить, а не молча пустые значения.
"""

from __future__ import annotations

import re
from typing import Any

# --- вспомогательные регулярки -------------------------------------------------

DAYS = r"(?:ПН|ВТ|СР|ЧТ|ПТ|СБ|ВС)"
SCHEDULE_RE = re.compile(
    rf"{DAYS}\s*[-–—]\s*{DAYS}\s*\d{{1,2}}[:.]\d{{2}}\s*[-–—]\s*\d{{1,2}}[:.]\d{{2}}"
)
TIME_RANGE_RE = re.compile(r"^\d{1,2}[:.]\d{2}\s*[-–—]\s*\d{1,2}[:.]\d{2}$")
PRICE_RE = re.compile(r"(от\s*)?(\d{1,3}(?:[ \u00a0]\d{3})+|\d{4,6})\s*(?:₽|руб)", re.IGNORECASE)
PHONE_800_RE = re.compile(r"8\s*\(\s*800\s*\)\s*[\d\s-]{7,12}")
PHONE_CITY_RE = re.compile(r"\+?\s*7?\s*\(\s*(?!800)\d{3,4}\s*\)\s*[\d\s-]{6,12}")
CALL_HOURS_RE = re.compile(r"С\s*\d{1,2}[:.]\d{2}\s*до\s*\d{1,2}[:.]\d{2}")
INN_RE = re.compile(r"ИНН\s*(\d{10,12})")
OGRN_RE = re.compile(r"ОГРН\s*(\d{13,15})")
LEGAL_RE = re.compile(
    r"(?:ООО|Общество\s+с\s+ограниченной\s+ответственностью)\s*[«\"]([^»\"]{2,60})[»\"]",
    re.IGNORECASE,
)

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
INCREASE_RE = re.compile(
    r"с\s+(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\s*(?:г\.?|года)?",
    re.IGNORECASE,
)

FAQ_QUESTIONS = (
    "Нужно ли отдельно оплачивать блок вождения?",
    "Как происходит оплата?",
    "Могу ли я изучать теорию дистанционно?",
    "Как проходят занятия?",
    "На каких авто проходит вождение?",
    "Можно ли приостановить обучение?",
    "Какие документы нужны, чтобы начать?",
)

# Опорные куски известных акций: ищем по фрагменту, в файл кладём фактический текст.
PROMO_MARKERS: tuple[tuple[str, str, str | None], ...] = (
    ("promo_tax_deduction", "Платишь официальный налог", "13%"),
    ("promo_student", "со студенческим", "1000 рублей"),
    ("promo_no_price_growth", "Не стараемся больше заработать", None),
    ("promo_young_mothers", "молодым мамам", "1000 рублей"),
    ("promo_up_to_30", "обновляем скидки", "до 30%"),
    ("promo_birthday", "именинникам", "1000 рублей"),
    ("promo_bring_friend", "Приведи друга", None),
    ("promo_free_online_lessons", "бесплатный доступ к онлайн-урокам", None),
    ("promo_vektor_family", "Vektor Family", None),
    ("promo_trial_lesson", "Пробное занятие", None),
    ("promo_lady_v", "Леди V", None),
    ("promo_rozygrysh", "розыгрыш", None),
    ("promo_return_money", "Успей вернуть", None),
    ("promo_gift_training", "обучение в подарок", None),
    ("promo_balaclava", "Балаклава в подарок", "Балаклава в подарок"),
)

LABEL_ADDRESS = "Адрес:"
LABEL_HOURS = "Время работы:"
LABEL_BREAK = "Перерыв:"


def _tail(line: str, label: str) -> str:
    """Возвращает часть строки после подписи, если подпись стоит в начале."""
    return line[len(label) :].strip(" :\u00a0")


def _digits(value: str) -> int | None:
    """Вытаскивает целое число из строки с пробелами и неразрывными пробелами."""
    cleaned = re.sub(r"[^\d]", "", value)
    return int(cleaned) if cleaned else None


# --- разделы -------------------------------------------------------------------


def parse_branches(lines: list[str]) -> list[dict[str, Any]]:
    """Собирает филиалы по подписям «Адрес» / «Время работы» / «Перерыв».

    Подписи и значения могут идти в разном порядке (в части городов перерыв напечатан
    перед своей подписью), поэтому внутри блока одного адреса значения разбираются по
    форме, а не по позиции.

    Аргументы:
        lines: строки плоского текста страницы.

    Возвращает:
        Список филиалов в схеме `branches.items`.
    """
    starts = [i for i, line in enumerate(lines) if line.startswith(LABEL_ADDRESS)]
    branches: list[dict[str, Any]] = []
    autodrome_mode = False

    for order, start in enumerate(starts):
        end = starts[order + 1] if order + 1 < len(starts) else len(lines)
        block = lines[start:end]

        # Заголовок секции ищем выше по странице: он переключает режим «автодром».
        lookback = lines[max(0, start - 8) : start]
        for line in lookback:
            low = line.lower()
            if "автодром" in low:
                autodrome_mode = True
            elif "филиал" in low:
                autodrome_mode = False

        address = _tail(block[0], LABEL_ADDRESS)
        rest = block[1:]
        if not address and rest:
            address = rest.pop(0)
        if not address:
            continue

        hours: str | None = None
        pause: str | None = None
        for line in rest:
            value = line
            if line.startswith(LABEL_HOURS):
                value = _tail(line, LABEL_HOURS)
            elif line.startswith(LABEL_BREAK):
                value = _tail(line, LABEL_BREAK)
            if not value:
                continue
            if hours is None and (SCHEDULE_RE.search(value) or "скоро открыт" in value.lower()):
                hours = value
            elif pause is None and TIME_RANGE_RE.match(value):
                pause = value

        branches.append(
            {
                "id": f"branch_{order + 1:02d}",
                "address": address,
                "district": None,
                "hours": hours,
                "break": pause,
                "is_autodrome": autodrome_mode,
                "note": None,
            }
        )
    return branches


def parse_prices(text: str) -> list[dict[str, Any]]:
    """Находит все денежные суммы на странице вместе с окружающей фразой.

    Цену за категорией парсер сам не закрепляет: на разных городах она стоит то в первом
    экране без привязки, то в карточке. Раскладывает по тарифам человек, здесь только факты.

    Аргументы:
        text: плоский текст страницы.

    Возвращает:
        Список словарей с суммой, признаком «от» и контекстом.
    """
    found: list[dict[str, Any]] = []
    seen: set[tuple[int, bool]] = set()
    for match in PRICE_RE.finditer(text):
        amount = _digits(match.group(2))
        if amount is None or amount < 1000:
            continue
        is_from = bool(match.group(1))
        key = (amount, is_from)
        if key in seen:
            continue
        seen.add(key)
        left = max(0, match.start() - 120)
        right = min(len(text), match.end() + 120)
        found.append(
            {
                "price": amount,
                "price_is_from": is_from,
                "context": " ".join(text[left:right].split()),
            }
        )
    return found


def parse_price_increase(text: str) -> dict[str, Any]:
    """Ищет анонс повышения цен с датой.

    Аргументы:
        text: плоский текст страницы.

    Возвращает:
        Словарь раздела `price_increase`; при отсутствии даты поля остаются пустыми.
    """
    match = INCREASE_RE.search(text)
    from_date = None
    if match:
        day, month, year = int(match.group(1)), MONTHS[match.group(2).lower()], int(match.group(3))
        from_date = f"{year:04d}-{month:02d}-{day:02d}"

    reason = None
    for phrase in ("будет повышение цен", "станет сильно выше", "сложнее, дороже и дольше"):
        idx = text.find(phrase)
        if idx != -1:
            left = max(0, idx - 200)
            right = min(len(text), idx + 200)
            reason = " ".join(text[left:right].split())
            break

    amount = None
    amount_match = re.search(r"повышение\D{0,40}?(\d{3,6})", text)
    if amount_match:
        amount = _digits(amount_match.group(1))

    return {"_source": None, "from_date": from_date, "amount": amount, "reason": reason}


def parse_faq(lines: list[str]) -> list[dict[str, Any]]:
    """Достаёт пары «вопрос — ответ» из блока ТОП-7.

    На части городов тело аккордеона в разметку не попадает; тогда ответ остаётся пустым,
    и это честнее, чем подставить формулировку из соседнего города.

    Аргументы:
        lines: строки плоского текста страницы.

    Возвращает:
        Список из семи вопросов; поле answer может быть None.
    """
    items: list[dict[str, Any]] = []
    question_set = {q.strip() for q in FAQ_QUESTIONS}
    for number, question in enumerate(FAQ_QUESTIONS, start=1):
        answer = None
        for i, line in enumerate(lines):
            if line.strip() != question:
                continue
            for candidate in lines[i + 1 : i + 4]:
                if candidate.strip() in question_set or len(candidate) < 25:
                    continue
                answer = candidate.strip()
                break
            if answer:
                break
        items.append({"id": f"faq_{number:02d}", "question": question, "answer": answer})
    return items


def parse_promos(text: str) -> list[dict[str, Any]]:
    """Собирает акции по опорным фрагментам известных формулировок.

    Аргументы:
        text: плоский текст страницы.

    Возвращает:
        Список акций в схеме `promos.items`; `valid_until` не угадывается и всегда None,
        дату проставляет человек по полю text.
    """
    promos: list[dict[str, Any]] = []
    for promo_id, marker, benefit in PROMO_MARKERS:
        idx = text.lower().find(marker.lower())
        if idx == -1:
            continue
        left = max(0, idx - 90)
        right = min(len(text), idx + 260)
        promos.append(
            {
                "id": promo_id,
                "name": None,
                "condition": None,
                "benefit": benefit,
                "valid_until": None,
                "text": " ".join(text[left:right].split()),
            }
        )
    return promos


def parse_company(text: str) -> dict[str, Any]:
    """Достаёт витринные показатели сети.

    Аргументы:
        text: плоский текст страницы.

    Возвращает:
        Словарь раздела `company`.
    """

    def grab(pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return _digits(match.group(1)) if match else None

    return {
        "_source": None,
        "years": grab(r"(\d{1,3})\s*лет\s*\n?\s*работы"),
        "graduates": grab(r"([\d\s\u00a0]{3,12})\+?\s*\n?\s*счастливых водител"),
        "first_try_pass_rate": grab(r"(\d{1,3})\s*%\s*\n?\s*сдачи с первого раза"),
        "cities": grab(r"(\d{1,3})\s*\n?\s*городов"),
    }


def parse_contacts(text: str, links: list[tuple[str, str]]) -> dict[str, Any]:
    """Собирает телефоны, юрлицо и ссылку на лицензию.

    Аргументы:
        text: плоский текст страницы.
        links: пары (текст ссылки, href) со страницы.

    Возвращает:
        Словарь раздела `contacts`.
    """
    federal = PHONE_800_RE.search(text)
    city = PHONE_CITY_RE.search(text)
    hours = CALL_HOURS_RE.search(text)
    inn = INN_RE.search(text)
    ogrn = OGRN_RE.search(text)
    legal = LEGAL_RE.search(text)

    license_url = None
    for label, href in links:
        if "лиценз" in label.lower():
            license_url = href
            break

    messengers = []
    joined = " ".join(href for _, href in links)
    for name, needle in (("Max", "max.ru"), ("WhatsApp", "whatsapp"), ("Telegram", "t.me")):
        if needle in joined:
            messengers.append(name)

    return {
        "_source": None,
        "phone_city": " ".join(city.group(0).split()) if city else None,
        "phone_federal": " ".join(federal.group(0).split()) if federal else None,
        "call_hours": " ".join(hours.group(0).split()) if hours else None,
        "messengers": messengers,
        "legal_entity": f"ООО «{legal.group(1)}»" if legal else None,
        "inn": inn.group(1) if inn else None,
        "ogrn": ogrn.group(1) if ogrn else None,
        "license": license_url,
    }


def find_conflicts(text: str) -> list[dict[str, Any]]:
    """Ищет места, где сайт сам себе противоречит.

    Проверяются срок рассрочки, набор телефонов и год возврата налога — именно они
    расходились на всех разобранных вручную городах.

    Аргументы:
        text: плоский текст страницы.

    Возвращает:
        Список расхождений в схеме `conflicts`.
    """
    conflicts: list[dict[str, Any]] = []

    terms = {m.group(0).strip() for m in re.finditer(r"рассрочк\w*[^.]{0,80}?месяц\w*", text, re.I)}
    if len(terms) > 1:
        conflicts.append(
            {
                "id": "conflict_installment_term",
                "field": "installment.term_months",
                "variants": [" ".join(t.split()) for t in sorted(terms)],
            }
        )

    phones = {" ".join(m.group(0).split()) for m in PHONE_800_RE.finditer(text)}
    phones |= {" ".join(m.group(0).split()) for m in PHONE_CITY_RE.finditer(text)}
    if len(phones) > 1:
        conflicts.append(
            {
                "id": "conflict_phone",
                "field": "contacts.phone_federal / phone_city",
                "variants": sorted(phones),
            }
        )

    years = set(re.findall(r"за обучение\s*\n?\s*в (\d{4}) году", text))
    if len(years) > 1:
        conflicts.append(
            {
                "id": "conflict_return_year",
                "field": "promos (год возврата)",
                "variants": [f"за обучение в {y} году" for y in sorted(years)],
            }
        )

    return conflicts


def build(
    slug: str,
    name: str,
    url: str,
    text: str,
    links: list[tuple[str, str]],
    today: str,
) -> dict[str, Any]:
    """Собирает итоговый документ города.

    Аргументы:
        slug: идентификатор города.
        name: название города.
        url: адрес городской страницы, он же `_source` разделов.
        text: плоский текст страницы.
        links: пары (текст ссылки, href).
        today: дата сбора в формате ГГГГ-ММ-ДД.

    Возвращает:
        Словарь по целевой схеме плюс служебный ключ `_review`.
    """
    lines = text.split("\n")

    branches = parse_branches(lines)
    prices = parse_prices(text)
    faq = parse_faq(lines)
    promos = parse_promos(text)
    company = parse_company(text)
    contacts = parse_contacts(text, links)
    increase = parse_price_increase(text)
    conflicts = find_conflicts(text)

    for section in (company, contacts, increase):
        section["_source"] = url

    review: list[str] = []
    if not branches:
        review.append("branches: не найдено ни одного «Адрес:» — проверить вёрстку вручную")
    if not prices:
        review.append("tariffs.price: сумм на странице не нашлось")
    if any(item["answer"] is None for item in faq):
        review.append("faq: часть ответов отсутствует в HTML, снять из браузера")
    review.append("promos: тексты выдернуты по окну вокруг маркера, обрезать хвосты руками")
    review.append("tariffs: цены не привязаны к категориям, разложить руками (см. prices_found)")
    if not contacts["legal_entity"]:
        review.append("contacts.legal_entity: юрлицо не найдено")

    return {
        "meta": {
            "city": name,
            "city_slug": slug,
            "domain": "avtoschool-vektor.ru",
            "collected_at": today,
            "version": 1,
        },
        "branches": {"_source": url, "items": branches},
        "tariffs": {"_source": url, "items": [], "prices_found": prices},
        "promos": {"_source": url, "items": promos},
        "price_increase": increase,
        "fleet": {"_source": url, "items": []},
        "theory_formats": {"_source": url, "items": []},
        "installment": {
            "_source": url,
            "term_months": None,
            "no_overpay": "без переплат" in text or "беспроцентн" in text,
            "down_payment": None,
            "methods": [],
        },
        "categories": {"_source": url, "items": []},
        "faq": {"_source": url, "items": faq},
        "documents": {"_source": url, "items": []},
        "company": company,
        "contacts": contacts,
        "groups": {"_source": None, "items": []},
        "conflicts": conflicts,
        "_review": review,
    }
