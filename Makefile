.PHONY: infra-up infra-down infra-logs infra-status infra-reset dev test lint

infra-up:
	./scripts/start-infra.sh

infra-down:
	docker compose -f infra/docker-compose.yml down

infra-logs:
	docker compose -f infra/docker-compose.yml logs -f

infra-status:
	docker compose -f infra/docker-compose.yml ps

infra-reset:
	docker compose -f infra/docker-compose.yml down -v

dev:
	python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest

lint:
	python -m ruff check .
