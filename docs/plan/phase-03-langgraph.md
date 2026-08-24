# Phase 3：LangGraph Workflow

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
