# Phase 11：Web UI / Authentication / Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立真实用户入口，让登录后的 `user_id`、`session_id`、完整会话历史、Agent Chat、Memory 和 LangGraph `thread_id` 能在真实 UI 中闭环验证。

**Architecture:** 前端采用开源 Next.js + React Chat UI，后端继续使用 FastAPI。认证由 FastAPI 签发 HttpOnly Session/JWT Cookie，后端从认证身份得到 `user_id`，禁止客户端直接提交并信任 `user_id`。每个会话拥有独立 `session_id`，第一阶段直接使用 `session_id` 作为 LangGraph `thread_id`，`task_id` 仍表示一次具体 Agent 执行。

**Tech Stack:** Next.js, React, FastAPI, PostgreSQL, LangGraph Persistence, existing Memory Store.

**Spec:** `docs/spec.md`; existing memory/conversation requirements in `docs/plan/phase-03-langgraph.md`.

## Global Constraints

- Backend remains FastAPI on local Python 3.12+; frontend is a separate local web application.
- `user_id`, `session_id`, and `task_id` must remain distinct concepts.
- `thread_id = session_id` is allowed for Phase 11, but database concepts remain separate.
- Complete conversation history is persisted and is not replaced by Short-term Memory or LangGraph Checkpoint.
- Authentication identity is authoritative on the backend; do not trust a client-supplied `user_id`.
- Agent execution internals remain execution events/evidence and are not blindly appended as user-visible chat messages.
- Existing Agent / LangGraph architecture must not be bypassed by the Web UI.

## 11.1 Authentication

Implement:

- User registration for local development.
- Login.
- Logout.
- Current-user endpoint.
- Password hashing.
- HttpOnly authentication cookie.
- Authentication dependency for protected APIs.
- Unauthorized requests return 401.

Database:

```text
users
- user_id
- email
- password_hash
- created_at
- updated_at
```

## 11.2 User / Session Ownership

All conversation APIs must derive `user_id` from the authenticated identity.

A session belongs to exactly one user:

```text
user_id
  └── session_id
       ├── messages
       └── LangGraph thread_id
```

A user must never be able to read another user's session by changing `session_id` in the URL.

## 11.3 Conversation API

Implement:

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

The chat endpoint must:

1. Resolve authenticated `user_id`.
2. Verify session ownership.
3. Persist the user message completely.
4. Invoke the existing Agent workflow with `thread_id=session_id`.
5. Persist the assistant message completely.
6. Return `task_id`, `session_id`, `user_id`, answer/report and citations.

## 11.4 Chat UI

Create a separate `web/` Next.js application.

UI must contain:

- Login / registration page.
- Left conversation list.
- New Chat button.
- Conversation switching.
- Message history.
- User / Assistant message bubbles.
- Citation/source rendering.
- Chat input and send action.
- Logout.
- Loading/error state.

Do not build a custom UI framework. Use established open-source React/Next.js primitives.

## 11.5 Identity / Session Display for Debugging

Development UI should visibly expose:

```text
User ID
Session ID
```

This is required for validating Memory and Persistence during development.

`task_id` may be shown in a debug/details area, but does not replace `session_id`.

## 11.6 Memory Integration

Verify that:

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

remain correctly separated.

Opening an old conversation must load complete persisted messages. Continuing it must reuse the same `session_id/thread_id`.

## 11.7 Streaming

Phase 11 should prefer SSE/event streaming for chat progress if the existing workflow can expose stable events. Streaming must not change the persistence semantics: complete user and assistant messages remain persisted independently of UI streaming.

## 11.8 Tests

### Unit

- Password hashing / verification.
- Authentication token/session validation.
- Current-user dependency.
- Session ownership checks.
- Request/response schemas.

### Integration

- Register → login → current user.
- Authenticated conversation creation.
- Session ownership enforcement.
- Message persistence.
- Chat → Agent workflow.
- `session_id → thread_id` mapping.
- Logout / unauthorized access.

### E2E

At minimum:

1. Register user A.
2. Login user A.
3. Create session A.
4. Send multiple messages.
5. Refresh page and reload complete history.
6. Create session B and switch between A/B.
7. Confirm user A cannot access another user's session.
8. Confirm `user_id`, `session_id`, `task_id` remain distinct.
9. Confirm Long-term Memory remains associated with `user_id` across sessions.
10. Confirm LangGraph Checkpoint resumes using `thread_id=session_id`.

## 11.9 Completion Criteria

Phase 11 is complete only when:

- A real user can register/login/logout from the Web UI.
- Backend derives `user_id` from authenticated identity.
- User can create and switch conversations.
- Complete message history survives page refresh.
- Session ownership is enforced server-side.
- Chat invokes the existing LangGraph workflow.
- `session_id` is used as the LangGraph `thread_id` without conflating it with `task_id`.
- Citation results are rendered in the UI.
- Memory and Checkpoint continue to work through the Web UI.
- Unit / Integration / E2E tests cover the complete identity → session → chat → persistence chain.
