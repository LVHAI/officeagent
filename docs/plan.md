# 企业智能分析与决策 Agent 平台执行计划

## 1. 实施目标

根据 `docs/spec.md` 实现一个可在 macOS 本地稳定运行、可调试、可测试的企业级 Multi-Agent 平台。

核心技术基线：

- LangChain DeepAgents：Multi-Agent Runtime
- LangGraph：Workflow / State / Checkpoint / 并行编排
- FastAPI：Backend API
- Milvus：Vector Database
- MCP：企业工具接入协议
- PostgreSQL：业务数据与 Agent 状态持久化
- Redis：缓存、会话及任务协调

### 运行原则

**当前开发环境不运行在 Docker 中。**

Backend、DeepAgents、LangGraph、RAG 等核心代码直接运行在 Mac 本机，便于：

- IDE 调试
- Python Debugger
- 单元测试
- Agent Step-by-Step 调试
- LangGraph 状态调试
- 热重载

Docker Compose 只负责启动当前项目依赖的**外部基础设施和模拟企业系统**，例如 PostgreSQL、Redis、Milvus、MinIO、MCP Server 等。

---

# 2. Phase 0：Mac + Docker Infrastructure

## 2.1 目标

在 macOS 上通过 Docker Desktop 一键启动所有外部依赖，Backend 保持本机运行。

目标开发拓扑：

```text
Mac
│
├── Backend（本机）
│   ├── FastAPI
│   ├── DeepAgents
│   ├── LangGraph
│   ├── RAG
│   └── MCP Client
│
└── Docker Desktop
    │
    ├── PostgreSQL
    ├── Redis
    ├── Milvus
    ├── etcd
    ├── MinIO
    ├── CRM MCP Server
    ├── Database MCP Server
    └── Mock Enterprise Services
```

## 2.2 Docker Compose

创建：

```text
infra/docker-compose.yml
```

Docker Compose 仅管理外部服务，不包含当前 Backend 开发环境。

服务包括：

- PostgreSQL
- Redis
- Milvus
- etcd
- MinIO
- CRM MCP Server
- Database MCP Server
- Knowledge MCP Server
- Report MCP Server

如部分 MCP Server 后续需要独立开发，也可以作为独立容器运行，Backend 通过 MCP Client 连接。

## 2.3 macOS 兼容性

必须验证：

- Apple Silicon：M1 / M2 / M3 / M4
- Intel Mac
- Docker Desktop
- `linux/arm64` 镜像优先
- 必要时兼容 `linux/amd64`
- 不依赖 NVIDIA CUDA
- 不要求 Mac GPU Container Runtime

LLM 默认通过 API Provider 调用；本地模型可选使用 Ollama，不将 CUDA / vLLM 作为 Mac 本地运行的强依赖。

## 2.4 一键启动

提供：

```bash
make infra-up
```

或：

```bash
./scripts/start-infra.sh
```

启动流程：

```text
检查 Docker Desktop
        ↓
检查环境变量
        ↓
docker compose up -d
        ↓
等待 PostgreSQL
        ↓
等待 Redis
        ↓
等待 Milvus
        ↓
等待 MCP Server
        ↓
执行 Health Check
        ↓
输出服务地址
```

同时提供：

```bash
make infra-down
make infra-logs
make infra-status
```

## 2.5 Service Health Check

所有基础服务必须具有健康检查或可检测连接状态。

启动脚本必须等待依赖真正 Ready 后再返回成功，不能仅依赖容器启动状态。

重点检查：

- PostgreSQL connection
- Redis connection
- Milvus connection
- MCP Server availability
- MinIO availability

## 2.6 Docker 数据持久化

使用 Docker volumes 保存：

- PostgreSQL data
- Milvus data
- MinIO data

默认 `docker compose down` 不删除数据。

提供独立清理命令：

```bash
make infra-reset
```

明确删除本地开发数据，避免误删。

---

# 3. Phase 1：Backend 本地开发环境

Backend 不进入 Docker。

本机安装并运行：

- Python 3.12+
- FastAPI
- LangChain
- DeepAgents
- LangGraph
- MCP SDK
- RAG dependencies

提供：

```bash
make dev
```

启动本机 FastAPI，并支持：

- Hot Reload
- IDE Debug
- Python Debugger
- Agent breakpoint
- LangGraph state inspection

配置通过 `.env` 指向 Docker 服务：

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

---

# 4. Phase 2：DeepAgents Multi-Agent Runtime

使用 **LangChain DeepAgents** 作为 Multi-Agent 核心框架。

实现：

- Supervisor DeepAgent
- Knowledge Agent
- Tool Agent
- Web Agent
- Report Agent
- Agent Delegation
- Planning
- Skills
- Tool Calling
- Agent Memory

职责划分：

```text
User
 ↓
Supervisor DeepAgent
 ↓
Task Planning
 ↓
Agent Delegation
 ├── Knowledge Agent
 ├── Tool Agent
 └── Web Agent
 ↓
Result Aggregation
 ↓
Report Agent
 ↓
Final Answer
```

---

# 5. Phase 3：LangGraph Workflow / State

LangGraph 不替代 DeepAgents，而负责底层 Workflow / State 能力。

实现：

- Workflow State
- Agent execution state
- Checkpoint
- Persistence
- Parallel execution
- Retry boundary
- Timeout boundary
- Human-in-the-loop
- Failure recovery

复杂任务允许 Knowledge / Tool / Web Agent 并行执行，避免串行等待。

---

# 6. Phase 4：RAG + Milvus

实现：

- Document Parser
- Document Type Classification
- Policy Node Chunking
- Parent-Child Retrieval
- Semantic Chunking
- Embedding
- Milvus Schema
- Vector Search
- Metadata Filter
- BM25 Search
- Result Merge
- Reranker
- Context Builder
- Citation

检索链路：

```text
Query
 ↓
Query Rewrite
 ↓
Vector Search + Metadata Filter + BM25
 ↓
Result Merge
 ↓
Reranker
 ↓
Top-K Context
 ↓
Citation-aware Answer
```

---

# 7. Phase 5：MCP Tool Platform

实现 MCP Client 和 Tool Discovery。

支持：

- CRM MCP Server
- Database MCP Server
- Knowledge MCP Server
- Report MCP Server

能力：

- Tool Discovery
- Dynamic Schema Loading
- Tool Invocation
- Timeout
- Retry
- Error Normalization
- Tool Result Source Tracking

---

# 8. Phase 6：Skill System

实现：

- Skill Registry
- Skill Metadata
- Skill Router
- Dynamic Tool Loading
- Skill-to-MCP mapping

Agent 首先加载 Skill 能力描述，再按任务动态加载具体 MCP Tools，避免将全部 Tool Schema 注入 Context。

---

# 9. Phase 7：Source / Trace / Audit

所有 Agent 输出统一保留 Source。

知识库来源：

- document
- page
- section
- article
- chunk_id

工具来源：

- system
- mcp_server
- tool
- request_id
- execution_time

Agent Trace：

- task_id
- agent_id
- parent_agent_id
- start_time
- end_time
- status
- error
- token usage

确保企业分析结果可以审计和追溯。

---

# 10. Phase 8：并发与可靠性

## 并发

使用 async / await，并允许独立 Agent 并行执行。

例如：

```text
Supervisor
    ↓
 ┌───────────────┐
 │               │
Knowledge     Tool        Web
 │               │           │
 └───────────────┴───────────┘
                 ↓
           Result Aggregator
```

要求：

- asyncio
- LangGraph parallel nodes
- Async MCP Client
- bounded concurrency
- per-task timeout
- global timeout
- cancellation propagation

## 错误处理

统一异常：

- AgentError
- ToolError
- RetrievalError
- ModelError
- MCPError
- InfrastructureError

机制：

- Retry with exponential backoff
- Timeout
- Fallback
- Circuit Breaker
- Partial Result
- Cancellation

一个 Agent 失败不能导致无依赖的其他 Agent 全部失败；Aggregator 必须能够处理 Partial Result。

---

# 11. Phase 9：测试

## Unit Test

测试：

- Chunking
- Embedding
- Retrieval
- Reranker
- Skill Router
- MCP Client
- Error Handling

## Agent Test

测试：

- Supervisor Planning
- Agent Delegation
- DeepAgents Tool Calling
- Agent State
- Checkpoint Recovery

## Integration Test

使用 Docker 中的真实基础设施测试：

- PostgreSQL
- Redis
- Milvus
- MCP Servers

Backend 仍然由测试进程在本机运行。

## Concurrency Test

测试：

- 多 Agent 并行
- MCP 并发调用
- 超时
- Cancellation
- Partial Failure
- 高并发任务隔离

## E2E Test

验证完整流程：

```text
User
 ↓
Supervisor DeepAgent
 ↓
Planning
 ↓
Knowledge + Tool + Web
 ↓
Aggregation
 ↓
Report Agent
 ↓
Final Answer + Sources
```

---

# 12. Phase 10：开发体验与验收

新开发者在 macOS 上应能够：

```bash
git clone <repository>
cd officeagent
cp .env.example .env
make infra-up
make dev
```

然后访问：

```text
http://localhost:8000
http://localhost:8000/docs
```

验收标准：

- Mac Apple Silicon 可运行
- Intel Mac 可运行
- Docker 仅运行外部依赖
- Backend 可本机 Debug
- DeepAgents Agent 可断点调试
- LangGraph State 可调试
- Milvus 正常工作
- MCP Server 正常工作
- 企业知识问答可运行
- 企业数据分析可运行
- 多 Agent 可并发执行
- MCP Tool 可动态发现和调用
- 自动生成分析报告
- 全链路 Trace 可追踪
- 服务异常可恢复
