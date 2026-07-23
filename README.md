# vektor-scraper

Сбор справочника автошколы «Вектор» по городам и пакет `vektor_directory` для
голосового бота. Проект сбора самодостаточен; бот ставит только пакет со
урезанными JSON и API импорта.

Нужен [uv](https://docs.astral.sh/uv/). Зависимости он поставит сам: `uv sync`.

## Порядок запуска (сбор)

От чистого листа — из корня проекта:

```bash
uv run vektor-scrape                            # страницы → data/raw, data/out
uv run python scripts/apply_sections.py         # тарифы, категории, автопарк, теория
uv run python scripts/finalize.py               # плоские слаги + ориентиры
uv run python scripts/build_index.py            # data/index.json
uv run python scripts/build_package_data.py     # урезанные JSON → vektor_directory/data
```

Или: `make scrape`, `make sections`, `make finalize`, `make index`.

Результат сбора:

```
data/raw/<slug>.html   сырая страница (после разбора: make clean-raw)
data/raw/<slug>.txt    плоский текст — для проверки спорных мест
data/out/<slug>.json   полный справочник по схеме
data/index.json        компактный индекс городов и филиалов
vektor_directory/data/ урезанные файлы для пакета бота
```

Повторный `vektor-scrape` берёт страницы из `data/raw`, сайт не дёргает.
Чтобы перекачать — `--force`.

```bash
uv run vektor-scrape --only krasnoyarsk omsk   # только эти города
uv run vektor-scrape --include-done            # включая СПб, Екатеринбург, Пермь
uv run vektor-scrape --external                # включая внешние домены
uv run vektor-scrape --force                   # игнорировать кэш
uv run vektor-scrape --pause 3                 # пауза между городами, секунд
uv run python scripts/finalize.py --metro      # опционально: метро с avtoshkoli.ru
```

## Пакет `vektor_directory`

То, что ставится в проект голосового бота. Данные внутри пакета (через
`importlib.resources`), после `uv build` лежат в колесе.

```python
from vektor_directory import (
    list_cities,
    list_branches,
    get_city,
    get_branch,
    city_enum,
    branch_enum,
    resolve_city,
)

city_enum()                      # слаги городов
branch_enum("perm")              # слаги филиалов города
get_city("perm")                 # мета для пересказа клиенту
get_branch("perm_chernyshevskogo")
resolve_city("Питер")            # → "sankt-peterburg"; "Москва" → None
```

В урезанных JSON остаются: `meta`, `branches`, `categories`, `fleet`,
`theory_formats`, `documents`, `faq` (только с ответом), `installment`, `contacts`.

Выброшены: `tariffs`, `promos`, `price_increase`, `conflicts`, `_review`, `groups`.
Цены с сайта занижены примерно вдвое — в API пакета их нет.

Пересобрать данные пакета после изменения `data/out`:

```bash
uv run python scripts/build_package_data.py
```

## Локальный API сбора: `directory.py` и `lookup.py`

Для проверки в этом репозитории (читают `data/out` или `VEKTOR_DATA`):

| Функция | Назначение |
|---|---|
| `list_cities()` | `{слаг, город, филиалов}` |
| `list_branches(city_slug)` | `{слаг, адрес, ориентир}` |
| `get_city` / `get_branch` | мета для пересказа |
| `data_dir()` | каталог с JSON городов |

```bash
uv run python lookup.py perm
uv run python lookup.py perm_chernyshevskogo
uv run python lookup.py          # интерактив: города, филиалы perm, помощь, выход
```

## Что осталось незаполненным

- **Цены.** На сайте занижены и часто без категории; в API не отдаются.
- **Расписание групп.** Есть только «Старт каждые …», конкретного расписания нет.
- **Районы и метро.** Почти везде `null`; `finalize --metro` тянет лишь то, что
  есть на avtoshkoli.ru, и то неполно.

## Проверка кода

```bash
make lint      # uv run ruff check .
make format    # uv run ruff format .
make test      # uv run pytest -q
make clean-raw # удалить data/raw/*.html, оставить *.txt
```
