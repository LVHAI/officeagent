# OfficeAgent

## Enterprise Intelligence Decision Agent Platform

基于 **LangChain DeepAgents + LangGraph + Milvus + MCP** 构建的企业级 Multi-Agent 智能分析与决策平台。

## Architecture

```text
Mac Host
│
├── Backend (local process)
│   ├── FastAPI
│   ├── DeepAgents
│   ├── LangGraph
│   └── RAG
│
└── Docker Desktop
    ├── PostgreSQL
    ├── Redis
    ├── Milvus
    ├── MinIO / etcd
    └── Mock Enterprise MCP Services
```

Backend intentionally runs on the Mac host so IDE and Python debugging remain straightforward. Docker Compose is used only for infrastructure and external enterprise-service simulations.

### Agent Flow

```text
User
 ↓
Supervisor DeepAgent
 ↓
Planning / Delegation
 ├── Knowledge Agent
 ├── Tool Agent
 └── Web Agent
 ↓
Result Aggregation
 ↓
Report Agent
 ↓
Final Answer + Sources
```

## Tech Stack

- LangChain DeepAgents — Multi-Agent runtime
- LangGraph — workflow/state/checkpoint orchestration
- Milvus — vector retrieval
- MCP — enterprise tool integration
- FastAPI — backend API
- PostgreSQL — persistence
- Redis — cache/session coordination
- Qwen / DeepSeek / OpenAI-compatible LLMs

## Local macOS Development

Requirements:

- macOS M1/M2/M3/M4 or Intel Mac
- Python 3.12+
- Docker Desktop

Setup:

```bash
cp .env.example .env
make infra-up
make dev
```

API:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

Health:

```bash
curl http://127.0.0.1:8000/health
```

Analysis API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H 'content-type: application/json' \
  -d '{"query":"分析华东区域客户流失原因"}'
```

## Docker Infrastructure

```bash
make infra-up
make infra-status
make infra-logs
make infra-down
make infra-reset
```

`infra-reset` deletes Docker volumes and therefore local development data.

## Documentation

- [Specification](docs/spec.md)
- [Implementation Plan](docs/plan.md)

## Roadmap

- [x] FastAPI local development foundation
- [x] DeepAgents runtime skeleton
- [x] LangGraph workflow skeleton
- [x] RAG chunking / hybrid retrieval foundation
- [x] Milvus repository foundation
- [x] MCP client / Skill registry foundation
- [x] Docker external infrastructure
- [x] CI test and compose validation
- [ ] Production-grade document parsers and embedding pipeline
- [ ] Production reranker integration
- [ ] Full enterprise MCP connectors
- [ ] Evaluation dataset and benchmark suite
