# Store locator: ближайший филиал по координатам

## Зачем

Раньше филиал клиенту подбирался текстовым совпадением по названию района. Поле `district` заполнено у трёх филиалов из всей сети — механизм фактически не работал. Расстояния и времени в пути не было вовсе: голосовой бот не мог честно ответить, «какой офис ближе» и «сколько ехать».

## Что нового

У всех **222** филиалов в `app/services/directory_service/data/*.json` проставлены координаты `lat` / `lon`. Добавлены две ручки и инфраструктура геокодирования.

### Ручки

**`GET /api/geocode`** — переводит произнесённое место в точку через выбранный геокодер.

```bash
curl -s -G "http://localhost:8000/api/geocode" \
  --data-urlencode "text=Солнечный" -d city_slug=krasnoyarsk
```

```json
{
  "text": "Солнечный",
  "lat": 56.115807,
  "lon": 92.932819,
  "found": true
}
```

**`GET /api/branches/nearest`** — считает расстояние до филиалов сети (гаверсинус) и отдаёт ближайшие в радиусе.

```bash
curl -s "http://localhost:8000/api/branches/nearest?lat=56.1152&lon=92.9186&city_slug=krasnoyarsk"
```

```json
[
  {
    "slug": "krasnoyarsk_slavy",
    "city": "Красноярск",
    "address": "ул. Славы, д. 12",
    "landmark": null,
    "distance_km": 0.43
  }
]
```

Параметры: `lat`/`lon` обязательны; `limit` (по умолчанию 3), `radius_km` (по умолчанию 50), `city_slug` — опционально.

### Провайдер геокодера

Выбирается настройкой `GEOCODER_PROVIDER`:

- `dadata` — API подсказок (основной);
- `dadata_cleaner` — стандартизация Cleaner;
- `nominatim` — OpenStreetMap через geopy.

Ключи: `DADATA_API_KEY`, `DADATA_SECRET_KEY` (для Cleaner), `GEOCODER_CONTACT` (для Nominatim).

### Модули (по одному предложению)

- `app/api/endpoints/directory.py` — регистрирует `/api/geocode` и `/api/branches/nearest` (маршрут `nearest` объявлен до `{branch_slug}`).
- `app/services/directory_service/api.py` — сервисный слой: геокодирование текста и сборка ответа ближайших филиалов.
- `app/services/directory_service/lookup.py` — подбор ближайших по формуле гаверсинуса с фильтром радиуса, автодромов и «скоро открытие».
- `app/services/directory_service/geo.py` — расстояние `great_circle` и проверка валидности точки.
- `app/services/directory_service/address.py` — нормализация адреса перед геокодером: срезает этаж, офис, ТЦ, скобочные уточнения; `extract_own_city` для филиалов в файле соседнего города.
- `app/services/directory_service/geocoders/` — реестр провайдеров; DaData с повтором без ограничения по городу при промахе; Nominatim.
- `app/schemas/directory.py` — модели `GeocodeResult` и `BranchNearby`.
- `app/core/config.py` — настройки `GEOCODER_*`, `DADATA_*`, дефолты `nearest_limit` / `nearest_radius_km`.
- `scripts/geocode_branches.py` — офлайн-простановка координат в JSON (`--city`, `--dry-run`, `--force`, `--only-missing`, `--provider`).

## Что не сломано

- Существующие ручки и схемы ответов не менялись — добавлены только новые.
- Порядок маршрутов проверен: `/api/branches/krasnoyarsk_slavy` по-прежнему отдаёт деталь филиала, а не перехватывается как `nearest`.
- Прежние тесты зелёные; целостность данных: у всех 222 филиалов заполнены `lat`/`lon`.

## Как проверить

Поднять справочник с ключами из `.env`:

```bash
set -a && source .env && set +a
uv run uvicorn app.main:app --port 8000
```

Опорная цепочка (район Солнечный → филиал на Славы ~0,43 км):

```bash
curl -s -G "http://localhost:8000/api/geocode" \
  --data-urlencode "text=Солнечный" -d city_slug=krasnoyarsk | python3 -m json.tool
# ожидание: found=true, точка района Солнечный в Красноярске

curl -s "http://localhost:8000/api/branches/nearest?lat=56.1152&lon=92.9186&city_slug=krasnoyarsk" \
  | python3 -m json.tool
# ожидание: первым krasnoyarsk_slavy, distance_km ≈ 0.43
```

Дополнительно:

- `/api/geocode` для «Купчино» с `city_slug=sankt-peterburg`, затем `/api/branches/nearest` по полученной точке — первым питерский филиал.
- `/api/branches/nearest` без `city_slug` по той же точке — тот же порядок.
- `/api/branches/nearest?lat=66&lon=100` — пустой список `[]`, статус 200.
- `/api/geocode?text=абырвалг` — `found=false`, статус 200.
- `/api/branches/krasnoyarsk_slavy` — деталь филиала жива.

Тесты:

```bash
uv sync --all-extras
uv run ruff format app tests scripts
uv run ruff check app tests scripts
uv run pytest -q
```

## Что осталось за скоупом

- Интеграция в мозг голосового бота (`vector_voice_agent`).
- Полнота и актуальность справочника филиалов (дубликаты адресов между городами вроде Артём/Владивосток).
- Время в пути (сейчас только расстояние по прямой).
