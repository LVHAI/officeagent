# Phase 5：Tool Agent / Skill / MCP

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
