# 企业智能分析与决策 Agent 平台执行计划

## Phase Overview

| Phase | 内容 |
|---|---|
| Phase 0 | 基础设施 |
| Phase 1 | Backend |
| Phase 2 | Supervisor DeepAgent |
| Phase 3 | LangGraph Workflow |
| Phase 4 | Knowledge Agent / RAG |
| Phase 5 | Tool Agent / Skill / MCP |
| Phase 6 | Web Agent |
| Phase 7 | Report Agent |
| Phase 8 | 错误处理与可观测性 |
| Phase 9 | 测试策略（TDD） |
| Phase 10 | 性能与 Context 控制 |
| Phase 11 | Web UI / Authentication / Conversation |

## Phase Documents

- [Phase 0：基础设施](plan/phase-00-foundation.md)
- [Phase 1：Backend](plan/phase-01-backend.md)
- [Phase 2：Supervisor DeepAgent](plan/phase-02-supervisor.md)
- [Phase 3：LangGraph Workflow](plan/phase-03-langgraph.md)
- [Phase 4：Knowledge Agent / RAG](plan/phase-04-knowledge-rag.md)
- [Phase 5：Tool Agent / Skill / MCP](plan/phase-05-tool-mcp.md)
- [Phase 6：Web Agent](plan/phase-06-web.md)
- [Phase 7：Report Agent](plan/phase-07-report.md)
- [Phase 8：错误处理与可观测性](plan/phase-08-observability.md)
- [Phase 9：测试策略（TDD）](plan/phase-09-testing.md)
- [Phase 10：性能与 Context 控制](plan/phase-10-context.md)
- [Phase 11：Web UI / Authentication / Conversation](plan/phase-11-web-auth-chat.md)

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
