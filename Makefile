SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help install run lookup parse lint format test api_tests \
	build_image up run_local_project logs logs_local_project down down_local_project \
	ps ok restart clean_raw

# --- зависимости ---

help: ## Показать список целей
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Синхронизировать зависимости
	uv sync

# --- локальный запуск ---

run: ## API локально на :8317 (uvicorn --reload)
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8317 --reload

lookup: ## Запуск vector-lookup
	uv run vector-lookup

parse: ## Прогон пайплайна парсинга
	uv run python -c "from app.services.parsing_service import pipeline; pipeline.run()"

# --- качество кода ---

lint: ## Проверить линтером
	uv run ruff check app/ tests/ api_tests/

format: ## Отформатировать
	uv run ruff format app/ tests/ api_tests/

test: ## Прогнать pytest
	uv run pytest -q

api_tests: ## Чёрные API-тесты
	uv run pytest api_tests -v

# --- docker ---

build_image: ## Собрать образ vector-kb
	docker build -t vector-kb:latest .

up: ## Поднять API в docker (detached)
	cd infra && docker compose --env-file .env -f docker-compose.yml up -d --build

run_local_project: ## Поднять API в docker (foreground)
	cd infra && docker compose --env-file .env -f docker-compose.yml up --build

restart: ## Пересоздать контейнер API
	cd infra && docker compose --env-file .env -f docker-compose.yml up -d --build --force-recreate

logs: ## Хвост логов API
	cd infra && docker compose --env-file .env -f docker-compose.yml logs -f api

logs_local_project: logs ## Алиас logs

down: ## Остановить стек
	cd infra && docker compose --env-file .env -f docker-compose.yml down

down_local_project: down ## Алиас down

ps: ## Состояние контейнеров
	cd infra && docker compose --env-file .env -f docker-compose.yml ps

ok: ## Проверить живость API
	curl -fsS http://127.0.0.1:8317/api/health && echo

# --- обслуживание ---

clean_raw: ## Удалить сырые HTML
	rm -f data/raw/*.html
