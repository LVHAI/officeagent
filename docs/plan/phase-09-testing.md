# Phase 9：测试策略（TDD）

所有核心功能先写测试，再实现。

### Unit Test

- Supervisor Plan Schema
- Delegation validation
- Agent Contract
- Skill Router
- MCP Discovery
- State Merge
- Retry
- Timeout
- Error normalization

### Integration Test

- Supervisor → LangGraph
- LangGraph → Knowledge
- LangGraph → Tool
- LangGraph → Web
- Aggregation → Replan
- Checkpoint → Resume

### Concurrency Test

验证三个独立 Agent 并行执行，而不是串行执行。

### E2E Test

至少覆盖：

1. 仅 Knowledge
2. 仅 Tool
3. 仅 Web
4. Knowledge + Tool 并行
5. Knowledge + Tool + Web 并行
6. 子 Agent 超时
7. 子 Agent 失败
8. Partial Result
9. Replan
10. Checkpoint Resume
