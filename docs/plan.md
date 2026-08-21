# 企业智能分析与决策 Agent 平台执行计划

## 1. 实施目标

根据 `docs/spec.md` 实现一个可在 macOS 本地稳定运行、可调试、可测试的企业级 Multi-Agent 平台。

核心技术基线：

- LangChain DeepAgents：Supervisor / Tool Agent Runtime
- LangGraph：Workflow / State / Checkpoint / Persistence / 并行编排
- FastAPI：Backend API
- Milvus：Vector Database
- MCP：企业工具接入协议
- PostgreSQL：业务数据与 Agent 状态持久化
- Redis：缓存、会话及任务协调
- Tavily：Web Agent 搜索工具

### 关键架构原则

**LangGraph 是整个 Multi-Agent 系统的 Workflow / State / Persistence / 并行编排层；DeepAgents 是部分 Agent 的 Runtime，而不是所有 Agent 的统一创建方式。**

系统使用 `create_deep_agent()` 创建核心 `SUPERVISOR_AGENT`。Supervisor 负责理解任务、规划任务，并决定调用一个或多个专业子 Agent。

专业子 Agent 根据职责选择最合适的实现方式：

- Knowledge Agent：普通 LangGraph Agent Node + RAG Pipeline，不强制使用 `create_deep_agent()`。
- Tool Agent：使用 `create_deep_agent()`，负责 Skill / MCP Tool 的动态选择和复杂工具编排。
- Web Agent：普通 Agent Node / ReAct Agent + Tavily Tool，不强制使用 `create_deep_agent()`。
- Report Agent：Structured Output / 普通 Agent Node，负责最终报告生成，不强制使用 `create_deep_agent()`。

目标架构：

```text
                         LangGraph
                            │
                            ▼
                  ┌────────────────────┐
                  │  SUPERVISOR_AGENT  │
                  │ create_deep_agent  │
                  └─────────┬──────────┘
                            │
                 Task Planning / Delegation
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
   Knowledge Agent      Tool Agent        Web Agent
      RAG Node        create_deep_agent     Tavily
          │                 │                 │
     Milvus/BM25          MCP/Skill          Search
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                     Result Aggregation
                            │
                            ▼
                      Report Agent
                            │
                            ▼
                  Final Answer + Sources
```

Supervisor 可以根据任务动态选择一个或多个子 Agent：

```text
简单知识问题
  → Knowledge Agent

企业数据查询
  → Tool Agent

最新外部信息
  → Web Agent

复杂企业分析
  → Knowledge + Tool + Web 并行/串行组合
```

**不是所有任务都需要调用所有 Agent，也不是所有 Agent 都需要 DeepAgents。**

### Supervisor Delegation 原则

`SUPERVISOR_AGENT` 是真正的 Multi-Agent 决策中心，而不是简单的 LangGraph Router。

Supervisor 必须能够：

- 理解用户目标
- 分解任务
- 判断需要哪些专业 Agent
- 委派一个或多个子 Agent
- 根据子 Agent 返回结果继续委派
- 判断是否可以并行执行
- 处理 Partial Result
- 在必要时重新 Delegation
- 最终形成可交付的分析上下文

LangGraph 不替代 Supervisor 的 Agentic Planning；LangGraph 负责执行 Supervisor 决策、维护 State、Checkpoint、并发和恢复。

```text
User
  ↓
LangGraph Workflow
  ↓
SUPERVISOR_AGENT (DeepAgent)
  ↓
Planning / Delegation
  ├── Knowledge Agent
  ├── Tool Agent (DeepAgent)
  └── Web Agent (Tavily)
  ↓
Result Aggregation
  ↓
Report Agent
  ↓
Final Answer
```

### 运行原则

**当前开发环境不运行在 Docker 中。**

Backend、DeepAgents、LangGraph、RAG 等核心代码直接运行在 Mac 本机，便于 IDE Debug、Python Debugger、Agent Step-by-Step 调试和 LangGraph State 调试。

Docker Compose 只负责启动当前项目依赖的外部基础设施和模拟企业系统，例如 PostgreSQL、Redis、Milvus、MinIO、MCP Server 等。

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
│   ├── SUPERVISOR_AGENT / DeepAgents
│   ├── LangGraph
│   ├── RAG
│   ├── Tool Agent / DeepAgents
│   └── MCP Client
│
└── Docker Desktop
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

重点检查：PostgreSQL、Redis、Milvus、MCP Server、MinIO。

## 2.6 Docker 数据持久化

使用 Docker volumes 保存 PostgreSQL、Milvus、MinIO 数据。

默认 `docker compose down` 不删除数据。提供独立的 `make infra-reset` 明确删除本地开发数据，避免误删。

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
- Tavily integration

提供：

```bash
make dev
```

启动本机 FastAPI，并支持 Hot Reload、IDE Debug、Python Debugger、Agent breakpoint 和 LangGraph state inspection。

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

# 4. Phase 2：Multi-Agent Runtime

## 4.1 SUPERVISOR_AGENT

使用 **LangChain DeepAgents `create_deep_agent()` 创建 `SUPERVISOR_AGENT`**。

Supervisor 是整个 Multi-Agent 系统的核心 Agent Runtime，负责：

- 理解用户任务
- Task Planning
- 判断需要哪些专业能力
- Agent Delegation
- 决定调用一个还是多个子 Agent
- 决定执行顺序
- 判断可并行任务
- 处理子 Agent 返回结果
- 必要时继续 Delegation
- 处理 Partial Result
- 汇总最终上下文

Supervisor 不应把所有 MCP Tools、RAG Tools、Tavily Tools 直接注入自身 Context；专业能力通过子 Agent Delegation 暴露。

## 4.2 Knowledge Agent

Knowledge Agent 使用普通 LangGraph Agent Node / 明确的 Agent Runtime，不强制使用 `create_deep_agent()`。

职责：

- Query Rewrite
- 企业知识库检索
- BM25
- Milvus
- Reranker
- Citation

Knowledge Agent 的检索流程尽量保持确定性，避免为了使用 DeepAgents 而增加不必要的 Agentic Loop。

## 4.3 Tool Agent

Tool Agent 使用 `create_deep_agent()`。

职责：

- Skill Selection
- Dynamic MCP Tool Discovery
- Tool Schema Loading
- MCP Tool Selection
- MCP Tool Invocation
- Tool Result Interpretation

Tool Agent 只加载当前 Skill 所需 MCP Tools，不把所有企业工具一次性注入 Context。

## 4.4 Web Agent

Web Agent 使用 Tavily Tool。

默认不使用 `create_deep_agent()`；如果未来 Web 搜索需要复杂多步规划，再单独评估是否引入 DeepAgents。

职责：

- Web Search
- Search Result Filtering
- Evidence Extraction
- URL / Source Tracking

## 4.5 Report Agent

Report Agent 默认使用普通 Agent Node + Structured Output，不强制使用 `create_deep_agent()`。

职责：

- 聚合 Knowledge / Tool / Web 结果
- 生成结构化分析报告
- 保留 Source / Citation
- 处理 Partial Result

## 4.6 Agent Contract

所有子 Agent 必须通过统一 State Contract 与 Supervisor 通信：

```text
AgentInput
- task_id
- parent_agent_id
- query
- context
- constraints

AgentOutput
- agent_id
- status
- result
- sources
- errors
- traces
- elapsed_ms
```

禁止通过隐式全局变量共享 Agent 状态。

---

# 5. Phase 3：LangGraph Workflow / State

LangGraph 不替代 DeepAgents，而负责整个系统的 Workflow / State / Persistence / 并行编排。

实现：

- Workflow State
- Supervisor ↔ Sub-Agent State
- Agent execution state
- Checkpoint
- Persistence
- Parallel execution
- Conditional routing
- Retry boundary
- Timeout boundary
- Human-in-the-loop
- Failure recovery

Supervisor 的 Agentic Delegation 与 LangGraph State 必须明确区分：

```text
Supervisor DeepAgent
    ↓
决定调用哪些子 Agent
    ↓
LangGraph
    ↓
执行 / 并发 / 持久化 / 恢复
```

复杂任务允许 Knowledge / Tool / Web Agent 并行执行，避免无依赖任务串行等待。

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

Knowledge Agent 负责调用该 Pipeline，不需要为了使用 RAG 而创建 DeepAgent。

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

MCP Tool 主要由 Tool Agent 使用。Supervisor 不直接依赖具体 MCP Tool 实现。

---

# 8. Phase 6：Skill System

实现：

- Skill Registry
- Skill Metadata
- Skill Router
- Dynamic Tool Loading
- Skill-to-MCP mapping

Tool Agent 首先加载 Skill 能力描述，再按任务动态加载具体 MCP Tools，避免将全部 Tool Schema 注入 Context。

Supervisor 只需要知道 Tool Agent 的能力边界，不需要知道每一个 MCP Tool 的底层 Schema。

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

Web 来源：

- URL
- title
- source
- retrieved_at

Agent Trace：

- task_id
- agent_id
- parent_agent_id
- start_time
- end_time
- status
- error
- token usage

特别记录 Supervisor → Sub-Agent 的 Delegation Trace：

```text
Supervisor
  ↓ delegate
Knowledge Agent
  ↓ result
Supervisor
  ↓ delegate
Tool Agent
```

确保企业分析结果可以审计和追溯。

---

# 10. Phase 8：并发与可靠性

## 并发

使用 async / await，并允许 Supervisor 委派的独立 Agent 并行执行。

例如：

```text
Supervisor DeepAgent
        ↓
   Task Planning
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

一个子 Agent 失败不能导致无依赖的其他 Agent 全部失败；Supervisor / Aggregator 必须能够处理 Partial Result，并决定是否需要重新 Delegation。

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
- Tavily Web Agent Adapter
- Error Handling

## Agent Test

测试：

- Supervisor Planning
- Supervisor Agent Delegation
- Knowledge Agent
- Tool Agent + DeepAgents
- Web Agent + Tavily
- Report Agent Structured Output
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

- Supervisor 并行 Delegation
- 多 Agent 并行
- MCP 并发调用
- 超时
- Cancellation
- Partial Failure
- 高并发任务隔离

## E2E Test

至少覆盖三类路径：

### 单 Agent

```text
User
 ↓
Supervisor DeepAgent
 ↓
Knowledge Agent
 ↓
Final Answer
```

### 多 Agent 并行

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

### Tool Agent

```text
User
 ↓
Supervisor
 ↓
Tool Agent DeepAgent
 ↓
Skill
 ↓
MCP Tool Discovery
 ↓
MCP Tool
 ↓
Result
 ↓
Supervisor
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
- Supervisor DeepAgent 可断点调试
- LangGraph State 可调试
- Supervisor 可以根据任务决定调用一个或多个子 Agent
- Knowledge Agent 正常工作
- Tool Agent + DeepAgents + MCP 正常工作
- Web Agent + Tavily 正常工作
- Report Agent 可以生成结构化报告
- Milvus 正常工作
- MCP Server 正常工作
- 企业知识问答可运行
- 企业数据分析可运行
- 多 Agent 可并发执行
- MCP Tool 可动态发现和调用
- 自动生成分析报告
- 全链路 Trace 可追踪
- Supervisor Delegation 可审计
- 服务异常可恢复
