.PHONY: infra-up infra-down infra-logs infra-status infra-reset seed-crm-db dev web-dev test lint

infra-up:
	bash scripts/start-infra.sh

infra-down:
	docker compose -f infra/docker-compose.yml down

infra-logs:
	docker compose -f infra/docker-compose.yml logs -f

infra-status:
	docker compose -f infra/docker-compose.yml ps

infra-reset:
	docker compose -f infra/docker-compose.yml down -v

seed-crm-db:
	bash scripts/seed-crm-db.sh

dev:
	python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web-dev:
	cd web && npm install && npm run dev

test:
	python -m pytest

lint:
	python -m ruff check .
