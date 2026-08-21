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

echo "Waiting for infrastructure services..."
for i in $(seq 1 30); do
  if docker compose -f "$COMPOSE_FILE" ps --status running | grep -q postgres \
    && docker compose -f "$COMPOSE_FILE" ps --status running | grep -q redis \
    && docker compose -f "$COMPOSE_FILE" ps --status running | grep -q milvus; then
    echo "Infrastructure containers are running."
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

echo "Infrastructure did not become ready in time." >&2
docker compose -f "$COMPOSE_FILE" ps
exit 1
