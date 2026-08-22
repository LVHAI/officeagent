#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

docker compose -f infra/docker-compose.yml exec -T postgres \
  psql -U officeagent -d officeagent < infra/postgres/seed_crm.sql

echo "CRM PostgreSQL schema and sample data are ready."
