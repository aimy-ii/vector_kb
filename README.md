# vektor-scraper

Сбор справочника автошколы «Вектор» по городам в JSON для голосового бота.
Отдельный одноразовый инструмент, к репозиторию `voice_bot` отношения не имеет.

Нужен только [uv](https://docs.astral.sh/uv/). Зависимости он поставит сам.

## Порядок запуска

От чистого листа — четыре шага из корня проекта:

```bash
uv run vektor-scrape                       # сбор страниц → data/raw, data/out
uv run python scripts/apply_sections.py    # тарифы, категории, автопарк, теория
uv run python scripts/finalize.py          # плоские слаги филиалов + ориентиры
uv run python scripts/build_index.py       # data/index.json для enum модели
```

Или через Make: `make scrape`, `make sections`, `make finalize`, `make index`.

Результат сбора:

```
data/raw/<slug>.html   сырая страница (после разбора можно удалить: make clean-raw)
data/raw/<slug>.txt    плоский текст — для проверки спорных мест
data/out/<slug>.json   справочник по схеме
data/index.json        компактный индекс городов и филиалов
```

Повторный `vektor-scrape` берёт страницы из `data/raw`, сайт не дёргает. Чтобы перекачать — `--force`.

Полезные флаги сбора:

```bash
uv run vektor-scrape --only krasnoyarsk omsk   # только эти города
uv run vektor-scrape --include-done            # включая СПб, Екатеринбург, Пермь
uv run vektor-scrape --external                # включая Липецк, Челябинск, Калининград
uv run vektor-scrape --force                   # игнорировать кэш
uv run vektor-scrape --pause 3                 # пауза между городами, секунд
```

Финализация с метро (опционально):

```bash
uv run python scripts/finalize.py --metro
```

## API `directory.py`

Офлайн-справочник для голосового бота. Города и филиалы адресуются плоскими слагами
(`perm`, `perm_chernyshevskogo`). Данные читаются из `data/out` (или из `VEKTOR_DATA`).

| Функция | Назначение |
|---|---|
| `list_cities()` | список `{слаг, город, филиалов}` для enum |
| `list_branches(city_slug)` | филиалы города: `{слаг, адрес, ориентир}` |
| `get_city(city_slug)` | мета города для пересказа клиенту |
| `get_branch(branch_slug)` | мета филиала (адрес, часы, ориентир, …) |
| `data_dir()` | каталог с JSON городов |

Цены в мете города нет намеренно: число на сайте занижено примерно вдвое против
реальной стоимости, вслух оно не идёт.

## `lookup.py`

Проверка справочника руками — слаг города или филиала:

```bash
uv run python lookup.py perm
uv run python lookup.py perm_chernyshevskogo
uv run python lookup.py          # интерактивный режим
```

В интерактиве: `города`, `филиалы perm`, `помощь`, `выход`.

## Что осталось незаполненным

- **Цены.** На сайте суммы занижены и часто без категории; в `directory` цена не отдаётся.
  В JSON остаются черновики в `tariffs` / `prices_found` и вопросы в `_review`.
- **Расписание групп.** На страницах есть только «Старт каждые …», конкретного
  расписания занятий нет — его в справочник не выдумываем.
- **Районы и метро.** В данных почти везде `null`: на сайте Вектора их нет, а
  `finalize --metro` тянет лишь то, что подписано на avtoshkoli.ru, и то неполно.

## Проверка кода

```bash
make lint      # uv run ruff check .
make format    # uv run ruff format .
make test      # uv run pytest -q
make clean-raw # удалить data/raw/*.html, оставить *.txt
```
