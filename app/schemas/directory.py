"""Схемы справочника городов и филиалов.

Цена отдаётся как витринное «от» с сайта вместе с обязательной оговоркой:
число занижено примерно вдвое против реального чека, поэтому `reliable`
остаётся False, пока заказчик не подтвердит настоящий прайс.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.constants.directory import PRICE_DISCLAIMER


class CityShort(BaseModel):
    """Краткая карточка города для списка."""

    slug: str = Field(title="Слаг города")
    name: str = Field(title="Город")
    branches_count: int = Field(title="Число филиалов")

    model_config = ConfigDict(
        json_schema_extra={"example": {"slug": "perm", "name": "Пермь", "branches_count": 5}}
    )


class CategoryInfo(BaseModel):
    """Категория обучения без цены."""

    code: str | None = Field(default=None, title="Категория")
    duration: str | None = Field(default=None, title="Срок обучения")
    start_frequency: str | None = Field(default=None, title="Старт групп")
    includes: list[str] = Field(default_factory=list, title="Что входит")


class VehiclesInfo(BaseModel):
    """Автопарк города для пересказа."""

    manual: list[str] = Field(default_factory=list, title="Механика")
    automatic: list[str] = Field(default_factory=list, title="Автомат")
    fleet_age: str | None = Field(default=None, title="Возраст парка")
    notes: list[str] = Field(default_factory=list, title="Особенности")


class DocumentInfo(BaseModel):
    """Документ, нужный для обучения."""

    name: str | None = Field(default=None, title="Что")
    stage: str | None = Field(default=None, title="Когда")


class PaymentInfo(BaseModel):
    """Условия оплаты без сумм."""

    installment_no_overpay: bool | None = Field(default=None, title="Рассрочка без переплат")
    methods: list[str] = Field(default_factory=list, title="Способы")


class FaqItem(BaseModel):
    """Пара вопрос–ответ без упоминаний цены."""

    question: str = Field(title="Вопрос")
    answer: str = Field(title="Ответ")


class PriceInfo(BaseModel):
    """Стоимость обучения так, как она указана на сайте.

    Число на сайте — маркетинговое «от» и заметно ниже реального чека: по сверке
    с независимыми площадками и отзывами учеников расхождение доходит до двух раз.
    Поэтому вместе с суммой всегда отдаётся оговорка в `note`, а `reliable` равно
    False, пока заказчик не подтвердит настоящий прайс.
    """

    amount: int | None = Field(default=None, title="Стоимость от, ₽")
    is_from: bool = Field(default=True, title="Цена указана как «от»")
    package: str | None = Field(default=None, title="Название пакета")
    reliable: bool = Field(default=False, title="Цена подтверждена")
    note: str = Field(title="Оговорка, которую нужно произнести")


class CityDetail(BaseModel):
    """
    Полная мета города для пересказа клиенту.

    Поле `price` содержит витринную сумму с сайта и оговорку: бот называет число
    вслух только вместе с `note`, пока `reliable` равно False.
    """

    slug: str = Field(title="Слаг города")
    name: str = Field(title="Город")
    branches_count: int = Field(title="Число филиалов")
    autodromes_count: int = Field(title="Число автодромов")
    categories: list[CategoryInfo] = Field(default_factory=list, title="Категории")
    vehicles: VehiclesInfo = Field(title="Автомобили")
    theory_formats: list[str] = Field(default_factory=list, title="Форматы теории")
    documents: list[DocumentInfo] = Field(default_factory=list, title="Документы")
    payment: PaymentInfo = Field(title="Оплата")
    faq: list[FaqItem] = Field(default_factory=list, title="Частые вопросы")
    phone: str | None = Field(default=None, title="Телефон")
    call_hours: str | None = Field(default=None, title="Приём звонков")
    messengers: list[str] = Field(default_factory=list, title="Мессенджеры")
    price: PriceInfo = Field(title="Стоимость с оговоркой")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "perm",
                "name": "Пермь",
                "branches_count": 4,
                "autodromes_count": 1,
                "categories": [
                    {
                        "code": "B",
                        "duration": "2,5 месяца обучения",
                        "start_frequency": "Старт каждые 2 недели",
                        "includes": [],
                    }
                ],
                "vehicles": {
                    "manual": ["Hyundai Solaris"],
                    "automatic": ["Kia Rio"],
                    "fleet_age": "не старше 2019 г",
                    "notes": [],
                },
                "theory_formats": ["Теорию можно изучать очно и онлайн"],
                "documents": [{"name": "Паспорт", "stage": "при заключении договора"}],
                "payment": {"installment_no_overpay": True, "methods": ["карта"]},
                "faq": [],
                "phone": "8 (800) 511-95-02",
                "call_hours": "С 7:30 до 23:00",
                "messengers": [],
                "price": {
                    "amount": 21950,
                    "is_from": True,
                    "package": "Базовый",
                    "reliable": False,
                    "note": PRICE_DISCLAIMER,
                },
            }
        }
    )


class BranchShort(BaseModel):
    """Краткая карточка филиала для списка."""

    slug: str = Field(title="Слаг филиала")
    address: str = Field(title="Адрес")
    landmark: str | None = Field(default=None, title="Ориентир")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "perm_chernyshevskogo",
                "address": "ул. Чернышевского, 28",
                "landmark": "ТЦ Колизей",
            }
        }
    )


class BranchDetail(BaseModel):
    """Полная информация о филиале для пересказа клиенту."""

    slug: str = Field(title="Слаг филиала")
    city: str = Field(title="Город")
    address: str = Field(title="Адрес")
    landmark: str | None = Field(default=None, title="Ориентир")
    district: str | None = Field(default=None, title="Район")
    metro: list[str] = Field(default_factory=list, title="Метро")
    place_type: str = Field(title="Тип точки")
    status: str = Field(title="Статус")
    working_hours: str | None = Field(default=None, title="Часы работы")
    break_time: str | None = Field(default=None, title="Перерыв")
    phone: str | None = Field(default=None, title="Телефон")
    note: str | None = Field(default=None, title="Примечание")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "perm_chernyshevskogo",
                "city": "Пермь",
                "address": "ул. Чернышевского, 28",
                "landmark": "ТЦ Колизей",
                "district": None,
                "metro": [],
                "place_type": "учебный офис",
                "status": "работает",
                "working_hours": "ПН-ПТ 10:00-19:00",
                "break_time": "14:00-15:00",
                "phone": "8 (800) 511-95-02",
                "note": None,
            }
        }
    )


class CityResolve(BaseModel):
    """Результат разбора разговорного названия города."""

    text: str = Field(title="Исходный текст")
    slug: str | None = Field(
        default=None,
        title="Слаг города",
        description="null, если города нет в сети — это валидный ответ, не ошибка",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"text": "Питер", "slug": "sankt-peterburg"}}
    )
