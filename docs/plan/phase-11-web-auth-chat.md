# Phase 11：Web UI / 用户认证 / 会话与聊天实施计划

> **给 Agent Worker：** 实现时必须遵循 TDD，先写测试，再实现功能；按任务逐项完成并使用复选框跟踪。

**目标：** 建立真实用户入口，让登录后的 `user_id`、`session_id`、完整会话历史、Agent Chat、Memory 和 LangGraph `thread_id` 能在真实 UI 中闭环验证。

**架构：** 前端采用开源 Next.js + React Chat UI，后端继续使用 FastAPI。认证由 FastAPI 签发 HttpOnly Session Cookie，后端从认证身份得到 `user_id`，禁止客户端直接提交并信任 `user_id`。每个会话拥有独立 `session_id`，第一阶段直接使用 `session_id` 作为 LangGraph `thread_id`，`task_id` 仍表示一次具体 Agent 执行。

**技术栈：** Next.js、React、FastAPI、PostgreSQL、LangGraph Persistence、现有 Memory Store。

**相关文档：** `docs/spec.md`；`docs/plan/phase-03-langgraph.md` 中已有的 Memory / Conversation 要求。

## 全局约束

- Backend 继续运行在本机 Python 3.12+；前端是独立的本地 Web 应用。
- `user_id`、`session_id`、`task_id` 必须保持为三个不同概念。
- Phase 11 允许 `thread_id = session_id`，但数据库中的概念仍然独立。
- 完整会话历史必须持久化，不能由 Short-term Memory 或 LangGraph Checkpoint 替代。
- 后端认证身份是唯一可信来源；禁止信任客户端提交的 `user_id`。
- Agent 内部执行过程仍属于 execution event / evidence，不能无条件追加为用户可见聊天消息。
- Web UI 不得绕过现有 Agent / LangGraph 架构。
- 本 Phase 必须通过数据库 Migration 建立所需持久化表，不允许依赖手工执行 `CREATE TABLE`。

## 11.1 用户认证

实现：

- 本地开发用户注册。
- 登录。
- 登出。
- 当前用户查询接口。
- 密码安全哈希。
- HttpOnly 认证 Cookie。
- 受保护 API 的认证依赖。
- 未认证请求返回 401。

数据库表：

```text
users
- user_id 主键
- email 唯一
- password_hash
- created_at
- updated_at

auth_sessions
- session_id 主键
- user_id 外键 → users.user_id
- token_hash
- expires_at
- created_at
- last_used_at
```

`auth_sessions` 用于保存登录认证状态；它与聊天 `conversation_sessions` 不是同一个概念。

## 11.2 用户 / 会话归属

所有会话 API 必须从当前认证身份取得 `user_id`。

一个聊天会话只属于一个用户：

```text
user_id
  └── conversation_session_id
       ├── messages
       └── LangGraph thread_id
```

用户不能通过修改 URL 中的 `session_id` 读取其他用户的会话。

## 11.3 Conversation 数据持久化

聊天会话必须使用 PostgreSQL 持久化：

```text
conversation_sessions
- session_id 主键
- user_id 外键 → users.user_id
- title
- created_at
- updated_at

conversation_messages
- message_id 主键
- session_id 外键 → conversation_sessions.session_id
- role
- content
- metadata JSONB
- created_at
```

约束：

- `conversation_sessions.user_id` 必须建立外键。
- `conversation_messages.session_id` 必须建立外键。
- 用户删除 / 清理会话时，其消息必须按明确的级联或事务策略处理。
- `session_id`、`user_id`、时间字段建立满足查询需求的索引。
- `conversation_messages` 必须保存完整用户消息和完整 Assistant 正式回复；执行事件、原始 Tool / Web / Knowledge 大结果不得直接无限写入消息表。

## 11.4 数据库 Migration

使用项目现有数据库 Migration 机制建立以下表：

```text
users
auth_sessions
conversation_sessions
conversation_messages
```

Migration 必须包含：

- 主键。
- 唯一约束。
- 外键约束。
- 必要索引。
- 时间字段默认值。
- 可重复部署的版本管理。

初始化数据库时使用 Migration 执行，而不是要求开发者手工建表。

测试环境必须能够自动执行 Migration 后运行测试。

## 11.5 Conversation API

实现：

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me

POST /api/v1/conversations
GET  /api/v1/conversations
GET  /api/v1/conversations/{session_id}
GET  /api/v1/conversations/{session_id}/messages
POST /api/v1/conversations/{session_id}/messages
DELETE /api/v1/conversations/{session_id}
```

聊天接口必须：

1. 获取当前认证用户的 `user_id`。
2. 验证聊天会话归属。
3. 完整持久化用户消息。
4. 使用 `thread_id=session_id` 调用现有 Agent Workflow。
5. 完整持久化 Assistant 正式回复。
6. 返回 `task_id`、`session_id`、`user_id`、answer/report 和 citations。

## 11.6 Chat UI

创建独立的 `web/` Next.js 应用。

UI 必须包含：

- 登录 / 注册页面。
- 左侧会话列表。
- 新建会话。
- 会话切换。
- 完整消息历史。
- User / Assistant 消息气泡。
- Citation / Source 展示。
- Chat 输入框与发送。
- 登出。
- 加载状态 / 错误状态。

不自行开发 UI 框架，使用成熟的开源 React / Next.js UI 基础组件。

## 11.7 调试身份 / 会话信息

开发环境 UI 应明确显示：

```text
User ID
Session ID
```

这是验证 Memory 和 Persistence 所必需的调试信息。

`task_id` 可以在调试 / 详情区域展示，但不能替代 `session_id`。

## 11.8 Memory 集成

验证：

```text
User
 ↓
Session
 ↓
Conversation History
 ↓
Short-term Memory
 ↓
Long-term Memory
 ↓
LangGraph Checkpoint
```

各层职责必须保持独立。

打开历史会话必须加载完整持久化消息；继续该会话必须复用相同的 `session_id/thread_id`。

## 11.9 Streaming

如果现有 Workflow 能稳定暴露事件，则优先使用 SSE / 事件流展示聊天进度。Streaming 不得改变持久化语义：完整用户消息和 Assistant 正式回复必须独立持久化，与 UI 是否流式展示无关。

## 11.10 测试

### Unit Test

- 密码哈希 / 校验。
- 认证 Session 校验。
- 当前用户依赖。
- 会话归属校验。
- Request / Response Schema。

### Integration Test

- 注册 → 登录 → 当前用户。
- 认证后创建会话。
- 会话归属隔离。
- 消息持久化。
- Chat → Agent Workflow。
- `session_id → thread_id` 映射。
- 登出 / 未认证访问。
- Migration → 数据库初始化 → API 持久化。

### E2E Test

至少覆盖：

1. 注册用户 A。
2. 用户 A 登录。
3. 创建会话 A。
4. 发送多条消息。
5. 刷新页面并重新加载完整历史。
6. 创建会话 B，并在 A / B 之间切换。
7. 确认用户 A 无法访问其他用户的会话。
8. 确认 `user_id`、`session_id`、`task_id` 保持独立。
9. 确认 Long-term Memory 按 `user_id` 跨 Session 保持关联。
10. 确认 LangGraph Checkpoint 使用 `thread_id=session_id` 恢复。
11. 确认数据库 Migration 后上述完整链路能够正常工作。

## 11.11 完成标准

Phase 11 只有同时满足以下条件才算完成：

- 用户可以从 Web UI 注册 / 登录 / 登出。
- Backend 从认证身份获得 `user_id`。
- 用户可以创建、查看和切换聊天会话。
- 完整消息历史在页面刷新后仍然存在。
- 服务端强制执行会话归属隔离。
- Chat 能调用现有 LangGraph Workflow。
- `session_id` 作为 LangGraph `thread_id` 使用，但不与 `task_id` 混淆。
- Citation 能在 UI 展示。
- Memory 与 Checkpoint 通过 Web UI 继续正常工作。
- PostgreSQL 中存在并通过 Migration 管理用户、认证 Session、聊天 Session、聊天消息表。
- Unit / Integration / E2E 测试覆盖完整的身份 → 会话 → 聊天 → 持久化链路。
