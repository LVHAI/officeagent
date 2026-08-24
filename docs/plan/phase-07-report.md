# Phase 7：Report Agent

Report Agent 负责：

- Aggregation
- Partial Result handling
- Structured Output
- Source / Citation preservation
- Final Answer

Report Agent 必须只消费 LangGraph Aggregation 后的结果，不直接绕过 Workflow 调用全部 Agent。
