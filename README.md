# OfficeAgent

## Enterprise Intelligence Decision Agent Platform

基于 DeepAgents + LangGraph + Milvus + MCP 构建的企业级 Multi-Agent 智能分析与决策平台。

## Features

- Multi-Agent 协作
- Supervisor Agent 任务规划
- 企业知识库 RAG 检索
- MCP 企业工具调用
- Skill 动态能力加载
- 自动分析报告生成

## Architecture

```
User
 |
Supervisor Agent
 |
+----------------+
| Knowledge Agent|
| Tool Agent     |
| Web Agent      |
+----------------+
 |
Report Agent
 |
Final Answer
```

## Tech Stack

- DeepAgents
- LangGraph
- Milvus
- MCP
- FastAPI
- Qwen / DeepSeek

## Documentation

- [Specification](docs/spec.md)

## Roadmap

- [ ] LangGraph workflow implementation
- [ ] RAG pipeline
- [ ] Milvus integration
- [ ] MCP Server implementation
- [ ] Multi-Agent evaluation system
