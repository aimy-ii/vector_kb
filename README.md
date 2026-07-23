# Vector KB

Справочник автошколы «Вектор» для голосового агента. Сервис отдаёт города и
филиалы по слагам, умеет разбирать разговорные названия («Питер» → `sankt-peterburg`)
и по запросу обновляет данные с сайта. Аутентификации нет: слушает внутреннюю
сеть рядом с агентом, наружу не смотрит.

Нужен [uv](https://docs.astral.sh/uv/). Порт по умолчанию — **8317**
(восьмитысячный на машине уже занят).

## Быстрый старт

### Локально

```bash
cp .env.example .env
uv sync
make run
# или: uv run uvicorn app.main:app --host 0.0.0.0 --port 8317 --reload
```

Проверка:

```bash
curl localhost:8317/api/health
curl localhost:8317/api/cities/enum
curl localhost:8317/api/branches/perm_chernyshevskogo
curl "localhost:8317/api/cities/resolve?text=Питер"
```

Терминальный поиск по слагу (без HTTP):

```bash
make lookup
# uv run vector-lookup perm
# uv run vector-lookup perm_chernyshevskogo
```

### Docker

```bash
cp infra/.env.example infra/.env
make run_local_project   # compose из infra/, порт 127.0.0.1:8317
make logs_local_project
make down_local_project
```

Собранные JSON и данные справочника лежат на именованных томах — результат
парсинга не пропадает при перезапуске контейнера.

## Эндпоинты

Префикс `/api`. Примеры ниже предполагают `http://127.0.0.1:8317`.

| Метод и путь | Назначение |
|---|---|
| `GET /api/health` | живость, число городов/филиалов, время загрузки |
| `GET /api/cities` | список городов: слаг, название, число филиалов |
| `GET /api/cities/enum` | плоский список слагов городов |
| `GET /api/cities/resolve?text=` | разговорное название → слаг или `null` |
| `GET /api/cities/{slug}` | полная мета города |
| `GET /api/cities/{slug}/branches` | филиалы города |
| `GET /api/cities/{slug}/branches/enum` | слаги филиалов города |
| `GET /api/branches/{slug}` | полная мета филиала |
| `POST /api/parse` | запуск обновления данных в фоне |
| `GET /api/parse/{job_id}` | статус задачи |
| `POST /api/reload` | перечитать файлы в память без перезапуска |

```bash
# живость
curl -s localhost:8317/api/health
# → {"status":"ok","cities_count":41,"branches_count":…,"loaded_at":"…"}

# enum городов
curl -s localhost:8317/api/cities/enum
# → ["abakan","achinsk",…]

# разговорное название
curl -s "localhost:8317/api/cities/resolve?text=Питер"
# → {"text":"Питер","slug":"sankt-peterburg"}

curl -s "localhost:8317/api/cities/resolve?text=Москва"
# → {"text":"Москва","slug":null}   # 200: города нет в сети

# филиал
curl -s localhost:8317/api/branches/perm_chernyshevskogo
# → {"slug":"perm_chernyshevskogo","city":"Пермь","address":"…",…}
```

Неизвестный слаг — `404` с понятным сообщением.

## Обновление данных

Полный прогон занимает около десяти минут, поэтому `POST /api/parse` отвечает
`202` и `job_id`, а работа идёт в фоне. Одновременно — не больше одной задачи:
вторая попытка вернёт `409` с текущим `job_id`.

```bash
curl -s -X POST localhost:8317/api/parse -H 'Content-Type: application/json' -d '{}'
# → {"job_id":"…","status":"pending"}

curl -s localhost:8317/api/parse/<job_id>
# → status: pending | running | done | failed
```

Тело запроса (все поля необязательны):

```json
{
  "only": ["omsk", "krasnoyarsk"],
  "force": false,
  "include_external": false,
  "include_done": false
}
```

- **`only`** — обновляет только перечисленные города; остальные файлы в
  справочнике остаются нетронутыми. Частичный прогон на пустом томе больше
  не стирает данные, пришедшие из образа.
- **`include_done`** — по умолчанию выключен. Санкт-Петербург, Екатеринбург и
  Пермь собраны вручную (районы, примечания, расхождения); пересборка с сайта
  ухудшит эти данные. Включайте только осознанно.
- Пайплайн **падает**, если после прогона число городов в каталоге справочника
  уменьшилось: задача получает статус `failed`, данные в памяти не меняются.

Порядок шагов: сбор страниц → разделы → финализация слагов и ориентиров →
индекс → урезанные JSON справочника. После успеха сервис сам перечитывает
справочник в память. При ошибке задача `failed`, данные в памяти не меняются.

История задач живёт только в памяти процесса и пропадает при перезапуске —
инстанс один, это осознанно.

## Почему в API нет цен

Число на сайте занижено примерно вдвое против реальной стоимости обучения
(проверено по сторонним площадкам и отзывам учеников). В схемах и ответах нет
полей с ценой, символа ₽ и слова «цена».

## Что в данных ещё пусто

- **Расписание групп.** На сайте только «Старт каждые …», конкретного
  расписания нет.
- **Районы и метро.** Почти везде пустые; опциональный шаг финализации тянет
  лишь то, что есть на avtoshkoli.ru, и то неполно.

## Переменные окружения

См. `.env.example` и `infra/.env.example`. Основные:

| Переменная | Смысл | По умолчанию |
|---|---|---|
| `API_PORT` | порт сервиса | `8317` |
| `LOG_LEVEL` | уровень логов | `INFO` |
| `RAW_DIR` | сырые страницы | `data/raw` |
| `OUT_DIR` | собранные JSON | `data/out` |
| `DIRECTORY_DATA_DIR` | урезанные JSON справочника | `app/services/directory_service/data` |
| `INDEX_PATH` | файл индекса | `data/index.json` |
| `LANDMARKS_PATH` | ориентиры 2ГИС | `app/services/parsing_service/landmarks.json` |
| `PARSE_PAUSE` | пауза между городами, сек | `1.5` |
| `REQUEST_TIMEOUT` | таймаут HTTP к сайту, сек | `30` |

## Makefile

| Цель | Действие |
|---|---|
| `make install` | `uv sync` |
| `make run` | uvicorn на `0.0.0.0:8317` с `--reload` |
| `make lookup` | терминальный поиск по слагу |
| `make parse` | полный прогон пайплайна в текущем процессе |
| `make lint` / `make format` | ruff |
| `make test` | unit/integration через TestClient |
| `make api_tests` | чёрный ящик к поднятому сервису |
| `make build_image` | сборка образа |
| `make run_local_project` | compose up --build |
| `make logs_local_project` | логи |
| `make down_local_project` | compose down |
| `make clean_raw` | удалить `data/raw/*.html` |

## Отступления от внутренних скиллов

1. Пакетный менеджер — **uv**, не `requirements.txt` и pip. В образе зависимости
   ставятся через `uv sync --frozen`.
2. Слоёв `models`, `crud` и Alembic **нет**: источник истины — JSON на диске,
   базы данных в проекте нет (ни SQLAlchemy, ни Redis, ни TaskIQ).

`prices.json` и `Автошкола_Вектор_2ГИС.md` в корне — исходные материалы, их
не трогаем.
