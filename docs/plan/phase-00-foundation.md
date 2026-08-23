# Phase 0：基础设施

Backend 不运行在 Docker 中。Docker Compose 只负责外部依赖和模拟企业服务。

目标拓扑：

```text
Mac
├── Backend
│   ├── FastAPI
│   ├── Supervisor DeepAgent
│   ├── LangGraph
│   ├── RAG
│   └── MCP Client
└── Docker Desktop
    ├── PostgreSQL
    ├── Redis
    ├── Milvus
    ├── etcd
    ├── MinIO
    └── MCP / Mock Enterprise Services
```

实现：

- `infra/docker-compose.yml`
- PostgreSQL
- Redis
- Milvus / etcd / MinIO
- CRM / Database / Knowledge / Report MCP Server
- Health Check
- Docker volume 持久化
- `make infra-up`
- `make infra-down`
- `make infra-status`
- `make infra-logs`
- `make infra-reset`

验证 Apple Silicon / Intel Mac，不依赖 CUDA.
