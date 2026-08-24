# Phase 11：Web 用户认证与聊天

## 目标

建立真实用户入口，让登录后的 `user_id`、`session_id`、完整会话历史、Agent Chat、Memory 和 LangGraph `thread_id` 能够通过真实 Web UI 闭环验证。

## 架构

```text
Web UI
  ↓
FastAPI 认证 / 会话 API
  ↓
用户身份 user_id
  ↓
聊天会话 session_id
  ↓
LangGraph thread_id
  ↓
Agent Workflow
  ↓
完整消息历史 / Memory / Checkpoint
```

前端使用成熟的开源 Next.js / React 方案，后端继续使用 FastAPI。

## 全局约束

- `user_id`、`session_id`、`task_id` 必须保持为三个不同概念。
- 第一阶段允许 `thread_id = session_id`。
- 后端认证身份是唯一可信来源，禁止信任客户端直接提交的 `user_id`。
- 完整会话历史必须独立持久化，不能由 Short-term Memory 或 LangGraph Checkpoint 替代。
- Agent 内部执行过程属于 execution event / evidence，不应无条件追加为用户可见聊天消息。
- Web UI 不得绕过现有 Supervisor + LangGraph Agent Workflow。

## 11.1 用户认证

实现：

- 用户注册。
- 用户登录。
- 用户登出。
- 当前用户信息查询。
- 密码安全哈希。
- HttpOnly 认证 Cookie。
- 受保护 API 的认证依赖。
- 未认证请求返回 401。

## 11.2 用户与会话

用户与聊天会话关系：

```text
user_id
  ├── session_id A
  │      └── messages
  │
  └── session_id B
         └── messages
```

必须保证：

- 一个聊天会话只属于一个用户。
- 用户只能读取、修改和删除自己的会话。
- 不允许通过修改 `session_id` 访问其他用户的数据。
- 页面刷新后可以恢复当前会话。
- 切换历史会话不会混淆不同 `session_id`。

## 11.3 会话 API

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

聊天请求必须：

1. 从认证身份获取 `user_id`。
2. 验证 `session_id` 是否属于当前用户。
3. 完整保存用户消息。
4. 使用 `thread_id=session_id` 调用现有 Agent Workflow。
5. 完整保存 Assistant 正式回复。
6. 返回 `user_id`、`session_id`、`task_id`、最终回答和 Citation。

## 11.4 Web Chat UI

创建独立的 `web/` Next.js 应用。

页面至少包含：

- 登录页面。
- 注册页面。
- 左侧历史会话列表。
- 新建会话。
- 会话切换。
- 完整消息历史。
- User / Assistant 消息气泡。
- Citation / Source 展示。
- 消息输入框和发送按钮。
- Loading 状态。
- Error 状态。
- Logout。

不自行开发 UI 框架，使用成熟的开源 React / Next.js UI 基础组件。

## 11.5 调试信息

开发环境必须能够直接看到：

```text
User ID
Session ID
```

`task_id` 可以放在调试 / 详情区域中展示，但不能替代 `session_id`。

这样可以直接验证：

```text
user_id
   ↓
session_id
   ↓
task_id
```

三者关系是否正确。

## 11.6 Memory / Persistence 集成

通过 Web UI 验证：

```text
User
 ↓
Session
 ↓
完整 Conversation History
 ↓
Short-term Memory
 ↓
Long-term Memory
 ↓
LangGraph Checkpoint
```

要求：

- 打开历史会话时加载完整消息。
- 继续历史会话时复用原来的 `session_id`。
- `session_id` 作为 LangGraph `thread_id`。
- Long-term Memory 按 `user_id` 跨 Session 使用。
- Checkpoint 只负责 Workflow 状态恢复。
- 完整消息历史不能被 Compression / Short-term Memory 替代。

## 11.7 Streaming

如果现有 Workflow 能稳定提供事件，则优先使用 SSE / 事件流展示 Agent 执行进度。

Streaming 不得改变消息持久化语义：

```text
用户完整消息
      ↓
持久化
      ↓
Agent Streaming
      ↓
Assistant 完整最终回复
      ↓
持久化
```

## 11.8 测试

### Unit Test

- 密码哈希与验证。
- 认证 Session 验证。
- 当前用户依赖。
- Session 所属用户校验。
- Request / Response Schema。

### Integration Test

- 注册 → 登录 → 当前用户。
- 登录 → 创建 Session。
- Session 用户隔离。
- 消息完整持久化。
- Chat → Agent Workflow。
- `session_id → thread_id` 映射。
- Logout / 未认证访问。
- Conversation History 查询。

### E2E Test

至少覆盖：

1. 注册用户 A。
2. 用户 A 登录。
3. 创建 Session A。
4. 发送多条消息。
5. 刷新页面。
6. 重新加载完整历史。
7. 创建 Session B。
8. 在 A / B 之间切换。
9. 注册并登录用户 B。
10. 验证用户 B 无法访问用户 A 的 Session。
11. 验证 `user_id`、`session_id`、`task_id` 各自保持正确含义。
12. 验证 Long-term Memory 可以跨 Session 使用。
13. 验证 LangGraph Checkpoint 可以使用 `thread_id=session_id` 恢复。

## 11.9 完成标准

Phase 11 完成必须同时满足：

- 用户可以通过 Web UI 注册、登录、登出。
- Backend 从认证身份获得真实 `user_id`。
- 用户可以创建、查看、删除和切换聊天会话。
- 完整消息历史可以持久化并在刷新后恢复。
- 服务端强制执行用户与 Session 隔离。
- Web Chat 能调用现有 LangGraph Workflow。
- `session_id` 与 `task_id` 不混淆。
- Citation 可以在 UI 展示。
- Memory 与 LangGraph Checkpoint 能通过真实 Web Chat 工作。
- Unit / Integration / E2E 测试覆盖身份 → Session → Chat → Persistence 完整链路。
