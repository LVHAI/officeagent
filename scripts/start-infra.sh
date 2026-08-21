#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="infra/docker-compose.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop for macOS first." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running." >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for infrastructure services to become healthy..."
for i in $(seq 1 60); do
  postgres_id=$(docker compose -f "$COMPOSE_FILE" ps -q postgres)
  redis_id=$(docker compose -f "$COMPOSE_FILE" ps -q redis)
  milvus_id=$(docker compose -f "$COMPOSE_FILE" ps -q milvus)

  postgres_health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$postgres_id" 2>/dev/null || true)
  redis_health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$redis_id" 2>/dev/null || true)
  milvus_health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$milvus_id" 2>/dev/null || true)

  mcp_running=$(docker compose -f "$COMPOSE_FILE" ps --status running --services | grep -E '^(crm-mcp|database-mcp|knowledge-mcp|report-mcp)$' | wc -l | tr -d ' ')

  if [[ "$postgres_health" == "healthy" \
    && "$redis_health" == "healthy" \
    && "$milvus_health" == "healthy" \
    && "$mcp_running" -eq 4 ]]; then
    echo "Infrastructure services are healthy."
    echo "PostgreSQL: localhost:5432"
    echo "Redis:      localhost:6379"
    echo "Milvus:     localhost:19530"
    echo "CRM MCP:    http://localhost:8101"
    echo "DB MCP:     http://localhost:8102"
    echo "Knowledge:  http://localhost:8103"
    echo "Report:     http://localhost:8104"
    exit 0
  fi
  sleep 2
done

echo "Infrastructure did not become healthy in time." >&2
docker compose -f "$COMPOSE_FILE" ps
exit 1
