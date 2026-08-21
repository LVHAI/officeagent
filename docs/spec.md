# 企业智能分析与决策 Agent 平台

## Enterprise Intelligence Decision Agent Platform

版本：V1.0

## 1. 项目概述

企业智能分析与决策 Agent 平台基于 DeepAgents + LangGraph + Milvus + MCP 构建，通过 Multi-Agent 协作实现企业知识查询、数据分析、系统调用、外部信息检索和自动报告生成。

## 2. 产品目标

用户通过自然语言提出业务问题，系统完成：

1. 用户意图理解
2. 任务复杂度判断
3. 自动任务规划
4. 企业知识检索
5. 企业系统工具调用
6. 外部信息获取
7. 综合分析
8. 报告生成

## 3. 总体架构

```
User
 |
Supervisor Agent
 |
Query Understanding
 |
+-------------------------------+
|               |               |
Knowledge     Tool Agent     Web Agent
Agent
|               |               |
Milvus          MCP          Search
 |
Result Aggregator
 |
Report Agent
 |
Final Answer
```

## 4. Agent 设计

### Supervisor Agent

职责：

- 用户意图理解
- 任务拆解
- Agent 调度
- 工作流管理

### Knowledge Agent

负责企业知识库检索和 RAG 问答。

### Tool Agent

负责 MCP 工具发现、Skill 加载以及企业系统调用。

### Web Agent

负责外部信息检索。

### Report Agent

负责生成结构化分析报告。

## 5. RAG 架构

技术：

- Milvus
- LangGraph
- BGE-M3
- BGE-Reranker-v2-m3

支持：

- 规章制度 Node 化入库
- Parent-Child Retrieval
- Semantic Chunking
- Multi-Route Retrieval

## 6. MCP Tool Agent

采用：

Skill + MCP 架构。

MCP Server：

- CRM MCP Server
- Database MCP Server
- ERP MCP Server
- Report MCP Server

示例工具：

```
customer.query
customer.history
sql.execute
schema.list
knowledge.search
report.generate
```

## 7. 数据追踪

所有 Agent 输出必须包含 Source 信息：

- 数据系统
- API 来源
- 时间
- 文档名称
- 页码
- 章节
- 条款

保证企业级可审计能力。

## 8. Backend 架构

```
backend
├── api
├── agents
│   ├── supervisor.py
│   ├── knowledge_agent.py
│   ├── tool_agent.py
│   ├── web_agent.py
│   └── report_agent.py
├── rag
│   ├── loader.py
│   ├── splitter.py
│   ├── embedding.py
│   └── retriever.py
├── tools
│   ├── mcp_client.py
│   ├── sql_tool.py
│   └── api_tool.py
```

## 9. 技术栈

### Agent

- DeepAgents
- LangGraph

### RAG

- Milvus
- BGE-M3

### LLM

- Qwen2.5
- Qwen3
- DeepSeek

### Backend

- FastAPI
- PostgreSQL
- Redis

## 10. 项目目标

打造一个可部署、可扩展、可用于企业场景的 Multi-Agent AI 平台。
