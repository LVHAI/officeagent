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

# 只启动外部基础设施，Backend/DeepAgents 仍在 Mac 本机运行，方便 IDE 调试。
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for infrastructure services..."
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" ps --format json | python3 -c '
import json, sys
services = [json.loads(line) for line in sys.stdin if line.strip()]
required = {"postgres", "redis", "etcd", "minio", "milvus", "crm-mcp", "database-mcp", "knowledge-mcp", "report-mcp"}
healthy = {s["Service"] for s in services if s.get("Health") == "healthy"}
raise SystemExit(0 if required <= healthy else 1)
'; then
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
