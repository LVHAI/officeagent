# 企业智能分析与决策 Agent 平台执行计划

## 1. 实施目标

根据 `docs/spec.md` 实现一个可在 macOS 本地稳定运行、可调试、可测试的企业级 Multi-Agent 平台。

核心技术基线：

- LangChain DeepAgents：Supervisor / Tool Agent Runtime
- LangGraph：Workflow / State / Checkpoint / Persistence / 并发编排
- FastAPI：Backend API
- Milvus：Vector Database
- MCP：企业工具接入协议
- PostgreSQL：业务数据与 Agent 状态持久化
- Redis：缓存、会话及任务协调
- Tavily：Web Agent 搜索工具

## 2. 关键架构原则（必须严格执行）

本项目采用 **Supervisor DeepAgent 决策 + LangGraph 执行编排** 的架构。两者职责必须严格分离，禁止反向设计。

```text
Supervisor DeepAgent
    ↓
决定调用哪些子 Agent
    ↓
LangGraph
    ↓
执行 / 并发 / 持久化 / 恢复
```

### 2.1 Supervisor DeepAgent 是决策中心

使用 `create_deep_agent()` 创建 `SUPERVISOR_AGENT`。

Supervisor 负责：

- 理解用户目标
- Task Planning
- Task Decomposition
- 判断需要调用哪些专业子 Agent
- 决定调用一个、多个或不调用子 Agent
- 决定子 Agent 的执行依赖关系
- 判断哪些任务可以并行
- 根据子 Agent 结果继续 Delegation / Replanning
- 判断 Partial Result 是否可以继续
- 形成最终分析上下文

**Supervisor 不是简单 Router。** 不允许用固定规则把每个请求无条件分发给 Knowledge / Tool / Web Agent。

**Supervisor 不直接注册全部 MCP Tools、RAG Tools、Tavily Tools。** 专业能力通过子 Agent 暴露，避免 Supervisor Context 随工具数量增长。

### 2.2 LangGraph 是执行层

LangGraph 不负责替代 Supervisor 的 Agentic Planning，而负责执行 Supervisor 已经做出的 Delegation 决策。

LangGraph 负责：

- Workflow State
- Agent execution
- Conditional routing
- 并发执行
- State merge / aggregation
- Checkpoint
- Persistence
- Resume / Recovery
- Retry boundary
- Timeout / cancellation boundary
- Failure isolation
- Human-in-the-loop

因此实现上必须保持：

```text
User Request
     ↓
Supervisor DeepAgent
     ↓
Delegation Plan
     ↓
LangGraph
     ├── Knowledge Agent ──┐
     ├── Tool Agent ──────┼── 并发执行（无依赖时）
     └── Web Agent ───────┘
     ↓
Aggregation / Replan
     ↓
Report Agent
     ↓
Final Answer
```

### 2.3 子 Agent 是独立能力单元

支持以下专业 Agent：

- **Knowledge Agent**：知识库检索与 RAG。
- **Tool Agent**：Skill → MCP 动态工具调用。
- **Web Agent**：Tavily 外部搜索。
- **Report Agent**：聚合结果并生成最终报告。

Knowledge / Web / Report 不强制使用 DeepAgents；只有需要复杂 Agentic Tool Planning 的 Tool Agent 使用 `create_deep_agent()`。

### 2.4 无依赖任务必须并发

Supervisor 返回多个无依赖 Delegation 时，LangGraph 必须将其编排为并行执行，而不是串行调用。

例如：

```text
Supervisor
    ↓
Delegation Plan
    ├── Knowledge Agent ─────┐
    ├── Tool Agent ──────────┼── asyncio / LangGraph parallel branches
    └── Web Agent ───────────┘
                              ↓
                          Aggregation
```

只有存在明确依赖时才允许串行：

```text
Knowledge Agent
      ↓
Tool Agent（依赖 Knowledge 结果）
      ↓
Report Agent
```

### 2.5 失败必须隔离并支持恢复

单个子 Agent 失败不能默认导致整个任务失败。

必须支持：

- Per-agent timeout
- Per-agent retry
- Failure isolation
- Partial Result
- Error normalization
- State checkpoint
- Workflow resume
- Replanning

例如：

```text
Knowledge ✓
Tool      ✗ timeout
Web       ✓
   ↓
Aggregation
   ↓
Supervisor 判断是否需要 Replan
   ↓
Report
```

### 2.6 Supervisor 与 LangGraph State 必须解耦

Supervisor 的规划结果必须转换成明确的结构化 Delegation Plan，LangGraph 根据 Plan 执行。

推荐 State：

```text
AgentState
- task_id
- query
- plan
- delegations
- execution_status
- agent_outputs
- errors
- traces
- replan_count
- final_context
- final_answer
```

Delegation：

```text
Delegation
- delegation_id
- agent_id
- task
- dependencies
- priority
- timeout_seconds
- status
- result
- error
```

禁止通过隐式全局变量共享 Agent 状态。

## 3. Phase 0：基础设施

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

验证 Apple Silicon / Intel Mac，不依赖 CUDA。

## 4. Phase 1：Backend

本机 Python 3.12+ 运行 FastAPI。

实现：

- 配置管理
- `/api/v1/analyze`
- Request / Response Schema
- request_id / task_id
- structured logging
- error handling
- timeout / cancellation
- health check

## 5. Phase 2：Supervisor DeepAgent

### 5.1 创建方式

必须使用：

```python
create_deep_agent(...)
```

创建 `SUPERVISOR_AGENT`。

### 5.2 Supervisor 输出

Supervisor 必须输出结构化 Delegation Plan，而不是直接执行所有工具。

示例：

```json
{
  "delegations": [
    {
      "agent_id": "knowledge",
      "task": "查询企业制度中关于销售退款的规定",
      "dependencies": []
    },
    {
      "agent_id": "tool",
      "task": "查询近三个月退款数据",
      "dependencies": []
    },
    {
      "agent_id": "web",
      "task": "查询最新行业退款趋势",
      "dependencies": []
    }
  ]
}
```

Supervisor 不得直接执行这三个 Agent 的 MCP / RAG / Tavily 工具；计划产生后交给 LangGraph。

### 5.3 动态 Delegation

必须支持：

```text
简单知识问题 → Knowledge
企业数据问题 → Tool
最新外部信息 → Web
复杂分析 → Knowledge + Tool + Web
```

具体选择必须由 Supervisor 根据任务决定，不能因为 Agent 已注册就全部执行。

## 6. Phase 3：LangGraph Workflow

建立唯一主 Workflow：

```text
START
  ↓
Supervisor DeepAgent
  ↓
Delegation Plan
  ↓
Parallel / Dependency Execution
  ↓
Aggregation
  ↓
需要补充？ ── Yes → Supervisor Replan
  │                    ↓
  │                 LangGraph
  │
  └── No
       ↓
Report Agent
       ↓
END
```

### 6.1 Graph Nodes

至少包含：

- `supervisor`
- `execute_plan`
- `aggregate`
- `replan`
- `report`

### 6.2 并发

无依赖 Delegation 使用 LangGraph 并行分支 / asyncio 执行。

必须验证：

- 3 个独立 Agent 是否真正并行
- 一个 Agent 慢不会阻塞其他 Agent
- State Merge 不发生覆盖
- 同一个 task_id 下状态一致

### 6.3 Checkpoint / Persistence

LangGraph Checkpointer 必须支持：

- task pause
- process interruption
- resume
- failure recovery
- state inspection

测试环境允许 InMemory Checkpointer；生产/开发持久化使用 PostgreSQL 等持久化存储。

Checkpoint 只负责 Workflow 执行状态的持久化与恢复，不替代会话历史和长期记忆。

### 6.4 Retry / Timeout

每个 Agent Execution 必须拥有独立：

- timeout
- retry policy
- cancellation handling
- error boundary

Retry 不得导致已经成功的其他 Agent 重复执行。

### 6.5 Conversation / Short-term / Long-term Memory

系统必须区分 **完整会话历史、Short-term Memory、Long-term Memory 和 LangGraph Checkpoint**，四者职责不能混淆。

#### 6.5.1 完整会话历史

所有用户与 Assistant 的正式对话消息必须完整、持久化保存，用于：

- 用户查看历史会话
- 打开并继续历史会话
- 会话历史查询 / 分页
- 后续审计与追溯

建议持久化结构：

```text
conversation_sessions
- session_id
- user_id
- created_at
- updated_at
- title / metadata

conversation_messages
- message_id
- session_id
- role
- content
- created_at
- metadata
```

完整历史保存不意味着每次请求都将全部历史消息发送给 LLM。

Agent 的内部执行过程不应全部伪装成用户可见的聊天消息。Supervisor Plan、Knowledge 原始 Chunks、MCP 调用参数/结果、Web 原始搜索结果等应作为独立 execution event / evidence 保存或记录，而不是无限追加到 conversation_messages。

#### 6.5.2 Short-term Memory

Short-term Memory 用于当前 Session 的上下文理解，不等同于完整消息历史，也不等同于 Checkpoint。

必须支持：

- 最近对话窗口
- 历史消息摘要
- 当前任务相关上下文
- 对过长历史进行裁剪 / 摘要
- 按 `session_id` / `thread_id` 隔离不同会话

原则：

```text
完整历史可以有 N 条消息
        ↓
Short-term Memory
        ↓
最近相关消息 + 历史摘要 + 当前任务上下文
        ↓
Agent Context
```

禁止因为完整历史持久化，就在每次 Agent 调用时无条件加载全部历史消息。

#### 6.5.3 Long-term Memory

Long-term Memory 用于保存跨 Session 仍然稳定、有价值的用户事实、偏好和业务上下文，而不是保存全部聊天记录。

第一阶段使用 PostgreSQL 进行结构化持久化，不要求立即引入向量数据库作为长期记忆存储。

建议结构：

```text
memories
- memory_id
- user_id
- memory_type
- key
- value
- confidence
- source_message_id
- created_at
- updated_at
```

Long-term Memory 必须支持：

- Memory Extraction：从完整会话中提取值得长期保存的信息
- Memory Retrieval：根据当前请求召回相关记忆
- Memory Update：新信息覆盖 / 修正旧事实
- Deduplication：避免同一事实重复写入
- Source Traceability：保留 `source_message_id`
- Session Independence：长期记忆可跨 Session 使用

例如：

```text
原始消息：
“以后我的报价默认使用美元。”
        ↓
Long-term Memory
        ↓
key = quotation_currency
value = USD
source_message_id = msg_xxx
```

不得将完整原始聊天记录直接作为 Long-term Memory 保存并在每次请求中全部注入 Context。

#### 6.5.4 Execution Events

Agent 内部执行过程建议独立持久化：

```text
execution_events
- event_id
- session_id
- task_id
- agent_id
- event_type
- payload / summary
- created_at
```

用于调试、审计、追踪和问题定位。

Knowledge 原始检索 Chunk、Tool 原始返回数据、Web 搜索结果等大对象应优先保存必要摘要、证据和引用，避免无限膨胀会话上下文。

#### 6.5.5 四层职责边界

```text
Raw Conversation
    = 用户可以查看的完整对话历史

Short-term Memory
    = 当前会话需要提供给 Agent 的上下文

Long-term Memory
    = 跨 Session 的稳定事实 / 偏好 / 业务上下文

LangGraph Checkpoint
    = Workflow 当前执行到哪里以及如何 Resume
```

四者必须独立建模，不能使用 Checkpoint 代替 Conversation Memory，也不能使用 Long-term Memory 代替完整历史消息。

## 7. Phase 4：Knowledge Agent / RAG

Knowledge Agent 使用确定性的 RAG Pipeline，不为了使用 DeepAgents 而增加不必要的 Agent Loop。

实现：

- Document Parser
- Markdown / semantic document parsing
- Parent-Child Document
- Semantic Chunking
- Embedding
- Milvus Schema
- Vector Search
- Metadata Filter
- BM25
- Result Merge
- Reranker
- Top-K Context
- Citation

流程：

```text
Query
 ↓
Query Rewrite
 ↓
Vector + BM25
 ↓
Merge
 ↓
Reranker
 ↓
Context Builder
 ↓
Citation Answer
```

Knowledge Agent 由 LangGraph 调度，不能自行绕过 Supervisor 直接被所有请求无条件调用。

## 8. Phase 5：Tool Agent / Skill / MCP

Tool Agent 使用 `create_deep_agent()`，但只暴露 Skill 层，不把全部企业 MCP Tool Schema 放入 Context。

严格执行：

```text
Supervisor
  ↓
Tool Agent
  ↓
Skill Selection
  ↓
读取 Skill metadata / SKILL.md
  ↓
Skill → MCP mapping
  ↓
Dynamic MCP Tool Discovery
  ↓
只加载当前 Skill 的 Tool Schema
  ↓
选择 MCP Tool
  ↓
Invocation
  ↓
Tool Result
```

要求：

- Skill metadata 只用于选择。
- 完整 `SKILL.md` 只在 Skill 被选择后加载。
- MCP Schema 只动态加载当前 Skill 声明的工具。
- Supervisor 不直接注册企业 MCP Tools。
- Tool Agent 初始 Context 不包含 CRM / SQL / Report 等全部 Tool Schema。
- MCP 数量增加时，Tool Agent Context 不随全部 MCP 数量线性增长。

示例：

```yaml
---
name: crm
description: CRM customer analysis
mcp_server: database
mcp_tools:
  - sql_query
---
```

## 9. Phase 6：Web Agent

Web Agent 使用 Tavily。

职责：

- Web Search
- Result Filtering
- Evidence Extraction
- URL / Source Tracking

Web Agent 不默认使用 DeepAgents。

只有 Supervisor 判断需要外部最新信息时才调用 Web Agent。

## 10. Phase 7：Report Agent

Report Agent 负责：

- Aggregation
- Partial Result handling
- Structured Output
- Source / Citation preservation
- Final Answer

Report Agent 必须只消费 LangGraph Aggregation 后的结果，不直接绕过 Workflow 调用全部 Agent。

## 11. Phase 8：错误处理与可观测性

统一记录：

- request_id
- task_id
- agent_id
- delegation_id
- parent_agent_id
- start_time
- elapsed_ms
- status
- error_type
- retry_count
- checkpoint_id

日志必须能够回答：

```text
Supervisor 决定了什么？
→ 调用了哪些 Agent？
→ 哪些并行？
→ 哪些成功/失败/超时？
→ 是否 Replan？
→ Checkpoint 在哪里？
→ 最终用了哪些结果？
```

## 12. Phase 9：测试策略（TDD）

所有核心功能先写测试，再实现。

### Unit Test

- Supervisor Plan Schema
- Delegation validation
- Agent Contract
- Skill Router
- MCP Discovery
- State Merge
- Retry
- Timeout
- Error normalization

### Integration Test

- Supervisor → LangGraph
- LangGraph → Knowledge
- LangGraph → Tool
- LangGraph → Web
- Aggregation → Replan
- Checkpoint → Resume

### Concurrency Test

验证三个独立 Agent 并行执行，而不是串行执行。

### E2E Test

至少覆盖：

1. 仅 Knowledge
2. 仅 Tool
3. 仅 Web
4. Knowledge + Tool 并行
5. Knowledge + Tool + Web 并行
6. 子 Agent 超时
7. 子 Agent 失败
8. Partial Result
9. Replan
10. Checkpoint Resume

## 13. Phase 10：性能与 Context 控制

重点验证：

- Supervisor Context 不包含全部 MCP Schema
- Tool Agent Context 不包含未选择 Skill 的 Schema
- 无依赖 Agent 不串行等待
- Agent 结果只传递必要 Context
- 大结果必须经过聚合 / 截断 / 摘要后再进入下一阶段
- 日志记录每个 Agent 的耗时和 Context 长度

目标是避免随着 Agent、Skill、MCP 数量增长导致 Context 爆炸和 Token 浪费。

## 14. 完成标准

只有同时满足以下条件才认为本计划完成：

- Supervisor 使用 DeepAgent 进行真实 Task Planning / Delegation。
- Supervisor 能动态决定调用哪些子 Agent，而不是全部调用。
- LangGraph 负责实际执行 Supervisor Plan。
- 无依赖子 Agent 能真正并发执行。
- 有依赖任务能够按依赖顺序执行。
- Checkpoint / Persistence / Resume 可用。
- 单个 Agent 失败不会无条件拖垮整个 Workflow。
- 支持 Partial Result 和 Replan。
- Tool Agent 遵循 Skill → MCP 动态加载边界。
- Knowledge / Web / Report 不被强制 DeepAgent 化。
- 所有关键路径具有 Unit / Integration / Concurrency / E2E 测试。
- 日志可以完整追踪 Supervisor 决策、LangGraph 执行和恢复过程。

最终架构必须始终保持：

```text
Supervisor DeepAgent
    ↓
决定调用哪些子 Agent
    ↓
LangGraph
    ↓
执行 / 并发 / 持久化 / 恢复
```
