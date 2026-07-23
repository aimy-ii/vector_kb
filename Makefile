SHELL := /bin/bash

.PHONY: install run lookup parse lint format test api_tests \
	build_image run_local_project logs_local_project down_local_project clean_raw

# --- зависимости ---

install:
	uv sync

# --- локальный запуск ---

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8317 --reload

lookup:
	uv run vector-lookup

parse:
	uv run python -c "from app.services.parsing_service import pipeline; pipeline.run()"

# --- качество кода ---

lint:
	uv run ruff check app/ tests/ api_tests/

format:
	uv run ruff format app/ tests/ api_tests/

test:
	uv run pytest -q

api_tests:
	uv run pytest api_tests -v

# --- docker ---

build_image:
	docker build -t vector-kb:latest .

run_local_project:
	cd infra && docker compose --env-file .env -f docker-compose.yml up --build

logs_local_project:
	cd infra && docker compose --env-file .env -f docker-compose.yml logs -f

down_local_project:
	cd infra && docker compose --env-file .env -f docker-compose.yml down

# --- обслуживание ---

clean_raw:
	rm -f data/raw/*.html
