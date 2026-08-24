# Phase 10：性能与 Context 控制

重点验证：

- Supervisor Context 不包含全部 MCP Schema
- Tool Agent Context 不包含未选择 Skill 的 Schema
- 无依赖 Agent 不串行等待
- Agent 结果只传递必要 Context
- 大结果必须经过聚合 / 截断 / 摘要后再进入下一阶段
- 日志记录每个 Agent 的耗时和 Context 长度

## 10.1 Context Compression

Context Compression 只控制进入后续 Agent Context 的数据，不修改完整 Conversation History、原始 AgentOutput 或持久化 evidence。

处理优先级：

```text
结构化裁剪
    ↓
去重
    ↓
限制字段 / Top-K
    ↓
截断
    ↓
超过阈值后才允许 LLM Summary
```

原则：

- 小结果不触发额外 LLM 调用。
- 可以通过结构化处理解决的问题，不增加 LLM 调用。
- LLM Summary 失败必须安全降级为截断。
- Compression 失败不能导致整个 Workflow 失败。
- 原始结果仍保留在 LangGraph state / execution evidence 中。
- 不允许完整 Tool / Web 原始结果无限进入 Supervisor / Report Context。

## 10.2 Knowledge / Tool / Web Context

Knowledge：只传递当前问题相关 Evidence、必要 Context 和 Citation。

Tool：优先保留查询结论、必要统计数据和与用户问题相关记录；原始大结果不进入后续 Agent Context。

Web：保留结论、关键证据、URL、title、source；不传递完整网页内容。

## 10.3 Citation Preservation

Context Compression 可以压缩 Evidence 内容，但不得丢失 Citation Metadata。

Knowledge Citation 至少保留：

- document
- document_id
- article / section
- chunk_id
- parent_id（Parent-Child 文档）
- chunk_type
- score / route（存在时）

最终 Report 必须能够从压缩后的上下文继续定位来源，而不是依赖 Summary 文本中人工拼接的引用。

## 10.4 Observability

Context Compression 日志至少记录：

- original_context_length
- compressed_context_length
- compression_ratio
- compression_method
- summary_llm_used
- fallback
- citation_count

目标是避免随着 Agent、Skill、MCP 数量增长导致 Context 爆炸和 Token 浪费。
