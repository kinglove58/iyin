.PHONY: install dev migrate seed sync-admin test lint typecheck eval discover discover-youtube crawl-approved-hybrid cloud-deploy crawl-fixtures reset build

install:
	uv sync --group dev
	cd apps/web && npm ci

dev:
	docker compose up --build

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed.py

sync-admin:
	docker compose run --rm api python -m scripts.sync_admin_credentials

test:
	uv run pytest
	cd apps/web && npm test

lint:
	uv run ruff check .
	cd apps/web && npm run lint

typecheck:
	uv run mypy
	cd apps/web && npm run typecheck

eval:
	uv run python -m services.evaluation.runner

build:
	cd apps/web && npm run build

discover:
	docker compose run --rm --user root api sh -c "cd services/crawler && scrapy crawl discovery"

discover-youtube:
	docker compose run --rm --user root api sh -c "cd services/crawler && scrapy crawl youtube_discovery"
	docker compose run --rm api python -m scripts.import_discovery --file /app/reports/crawler-output.jsonl

crawl-approved-hybrid:
	docker compose run --rm --user root api sh -c "cd services/crawler && scrapy crawl approved_content -a approved_file=/app/fixtures/approved-sources.json -a zyte_mode=fallback"

cloud-deploy:
	cd services/crawler && uvx --from shub shub deploy $(SCRAPY_CLOUD_PROJECT_ID)

crawl-fixtures:
	docker compose --profile fixtures up -d fixture-site
	docker compose run --rm --user root api sh -c "cd services/crawler && scrapy crawl approved_content -a approved_file=/app/fixtures/approved-docker-sources.json"
	docker compose run --rm api python -m scripts.fixture_ingestion

reset:
	docker compose down -v --remove-orphans
