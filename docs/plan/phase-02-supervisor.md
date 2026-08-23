# Phase 2：Supervisor DeepAgent

### 5.1 创建方式

必须使用：

```python
create_deep_agent(...)
```

创建 `SUPERVISOR_AGENT`。

### 5.2 Supervisor 输出

Supervisor 必须输出结构化 Delegation Plan，而不是直接执行所有工具。

示例：

```json
{
  "delegations": [
    {
      "agent_id": "knowledge",
      "task": "查询企业制度中关于销售退款的规定",
      "dependencies": []
    },
    {
      "agent_id": "tool",
      "task": "查询近三个月退款数据",
      "dependencies": []
    },
    {
      "agent_id": "web",
      "task": "查询最新行业退款趋势",
      "dependencies": []
    }
  ]
}
```

Supervisor 不得直接执行这三个 Agent 的 MCP / RAG / Tavily 工具；计划产生后交给 LangGraph。

### 5.3 动态 Delegation

必须支持：

```text
简单知识问题 → Knowledge
企业数据问题 → Tool
最新外部信息 → Web
复杂分析 → Knowledge + Tool + Web
```

具体选择必须由 Supervisor 根据任务决定，不能因为 Agent 已注册就全部执行。
