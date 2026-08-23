---
name: sql
description: Generic read-only PostgreSQL analysis through the Database MCP Server.
---

# Database SQL

Use the **Database MCP Server** for generic PostgreSQL schema discovery and
read-only analytical SQL.

This is a **generic database skill**, not a domain-specific business workflow.
When a request clearly matches a domain skill such as `CRM Customer Analysis`,
the domain skill takes precedence and this skill should only provide the
underlying SQL/database guidance it needs.

## Responsibilities

Use this skill for:

- generic PostgreSQL schema discovery
- read-only analytical SQL
- aggregation and reporting queries that are not covered by a domain-specific skill
- database inspection when no more specific domain skill applies

## Skill priority

- Prefer domain-specific skills over this generic SQL skill when the user's request is clearly domain-specific.
- For CRM customer requests, prefer `CRM Customer Analysis` and use Database MCP `sql_query` as its data-access mechanism.
- Do not independently compete with a domain-specific skill for the same request.
- Do not invent or substitute domain workflows that are defined by another skill.

## Tool policy

- Discover Database MCP tools before invocation.
- Discover schema before constructing unfamiliar queries.
- Never invent table names or column names.
- Default to read-only SQL: only `SELECT` / `WITH` queries are permitted.
- Bound result sizes with selective predicates and `LIMIT` where appropriate.
- Avoid unbounded scans when a narrower query can answer the request.
- Respect database query execution time limits.
- Preserve database source metadata, including database, tool name, SQL, and returned columns when available.
- Never modify database schema or data through this skill.

## CRM routing example

For a request such as:

> 查询客户 C001 的基本信息和消费情况

route the request through the `CRM Customer Analysis` skill rather than treating
it as a generic SQL task. The CRM skill uses the Database MCP `sql_query` tool
against the `customers` and `customer_orders` tables.
