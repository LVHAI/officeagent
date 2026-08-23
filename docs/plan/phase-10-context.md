# Phase 10：性能与 Context 控制

重点验证：

- Supervisor Context 不包含全部 MCP Schema
- Tool Agent Context 不包含未选择 Skill 的 Schema
- 无依赖 Agent 不串行等待
- Agent 结果只传递必要 Context
- 大结果必须经过聚合 / 截断 / 摘要后再进入下一阶段
- 日志记录每个 Agent 的耗时和 Context 长度

目标是避免随着 Agent、Skill、MCP 数量增长导致 Context 爆炸和 Token 浪费。
