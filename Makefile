.PHONY: scrape sections finalize index lookup lint format test clean-raw

scrape:
	uv run vektor-scrape

sections:
	uv run python scripts/apply_sections.py

finalize:
	uv run python scripts/finalize.py

index:
	uv run python scripts/build_index.py

lookup:
	uv run python lookup.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest -q

clean-raw:
	rm -f data/raw/*.html
