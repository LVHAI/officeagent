# 企业智能分析与决策 Agent 平台

## Enterprise Intelligence Decision Agent Platform

版本：V1.0

---

# 1. 项目概述

## 1.1 项目背景

企业内部存在大量分散的数据和知识资源：

### 非结构化数据

* 企业规章制度
* 产品文档
* 技术资料
* 合同文件
* 培训资料
* FAQ
* 销售手册

### 结构化数据

* CRM 客户数据
* 订单数据
* 销售数据
* ERP 数据
* 财务数据

传统企业系统存在以下问题：

* 数据查询依赖人工
* 企业知识无法快速利用
* 多系统数据无法统一分析
* 销售和管理决策效率低

本项目构建一个基于 **DeepAgents + LangGraph + Milvus + MCP** 的企业智能 Agent 平台。

通过 Multi-Agent 协作，实现：

* 企业知识查询
* 企业数据分析
* 系统 API 调用
* SQL 数据查询
* 外部信息检索
* 自动生成分析报告

---

# 2. 产品目标

构建一个企业级 AI 助手。

用户通过自然语言提出问题：

例如：

> 分析今年客户流失原因，并结合行业趋势给出销售优化建议。

系统自动：

1. 理解用户意图
2. 判断任务复杂度
3. 制定执行计划
4. 查询企业知识库
5. 调用企业系统工具
6. 获取外部信息
7. 综合分析
8. 自动生成报告

---

# 3. 总体架构

```text
                         User

                          |

                          |

                 Supervisor Agent

                          |

              Query Understanding

                          |

        ---------------------------------

        |              |                |

 Knowledge Agent   Tool Agent      Web Agent

        |              |                |

     Milvus          MCP             Search


        ---------------------------------

                          |

                  Result Aggregator

                          |

                   Report Agent

                          |

                    Final Answer
```

---

# 4. Agent 架构设计

## 4.1 Supervisor Agent

职责：

* 用户意图理解
* 任务拆解
* Agent 调度
* 执行流程管理

例如：

用户：

> 分析华东区域客户流失原因

生成任务计划：

```json
{
 "tasks":[
   "查询CRM客户数据",
   "查询销售管理制度",
   "分析行业趋势",
   "生成分析报告"
 ]
}
```

---

# 5. Query 智能路由

系统根据问题复杂度选择执行策略。

## 5.1 简单问题

例如：

> 公司年假制度是什么？

执行流程：

```text
User

↓

Supervisor Agent

↓

Knowledge Agent

↓

Milvus Retrieval

↓

Answer
```

只调用知识库。

---

## 5.2 复杂问题

例如：

> 分析客户流失原因，并制定销售策略。

执行流程：

```text
Supervisor Agent

↓

Task Planning

↓

--------------------------------

Knowledge Agent

Tool Agent

Web Agent

--------------------------------

↓

Report Agent

↓

Final Answer
```

---

# 6. 企业知识库设计

## 6.1 技术方案

知识库统一使用：

* Milvus

RAG 框架：

* LangGraph

Embedding 模型：

国产优先：

* BGE-M3
* BGE-large-zh
* GTE
* m3e

大语言模型：

国产优先：

* Qwen2.5
* Qwen3
* DeepSeek

---

# 7. 文档入库策略

系统根据文档类型选择不同处理方式。

整体流程：

```text
Document

↓

Document Parser

↓

Document Type Classification

↓

Chunk Strategy

↓

Embedding

↓

Milvus
```

---

# 8. 规章制度类文档处理

## 8.1 使用场景

适用于：

* 公司制度
* 管理规范
* 审批流程
* 操作规范

特点：

具有明确结构：

* 第几章
* 第几条
* 第几款

---

## 8.2 Node 化入库

规章制度不采用普通文本切割。

而是：

> 一条规则对应一个 Node。

例如：

原文：

```
销售管理制度

第三章 客户管理

第十二条：

客户等级分为A级、B级。

第十三条：

A级客户享受特殊折扣。
```

转换：

```json
{
"id":"policy_00001",

"text":
"第十二条：客户等级分为A级、B级",

"metadata":{

"document":"销售管理制度.pdf",

"department":"销售部",

"chapter":"第三章 客户管理",

"article":"第十二条",

"page":15

}

}
```

---

## 8.3 优势

用户查询：

> A级客户有什么权益？

返回：

```
来源：
销售管理制度.pdf

章节：
第三章 客户管理

条款：
第十三条
```

实现：

* 精确定位来源
* 企业审计能力
* 可追溯引用

---

# 9. 大小文档处理方式

## 9.1 使用场景

适用于：

* 产品白皮书
* 技术文档
* 企业手册

特点：

文档包含：

* 摘要
* 详细内容

---

## 9.2 Parent-Child Retrieval

结构：

```text
Document

|

Summary

|

Detail Chunk
```

示例：

父节点：

```json
{
"id":"product_001",

"summary":

"CRM客户管理系统"
}
```

子节点：

```json
{
"parent_id":"product_001",

"content":

"客户画像模块支持..."
}
```

Embedding：

对子节点进行向量化。

metadata：

```json
{
"document":"CRM产品白皮书",

"department":"产品部",

"section":"客户画像模块",

"parent_id":"product_001"

}
```

---

# 10. 普通文档语义切割

## 10.1 使用场景

适用于：

* FAQ
* 培训资料
* 普通说明文档

---

## 10.2 Semantic Chunking

不采用固定长度切割。

流程：

```text
Sentence Split

↓

Embedding Similarity

↓

Semantic Boundary Detection

↓

Chunk
```

生成：

```json
{
"text":
"客户开户流程...",


"metadata":{

"department":"客服部",

"document":"FAQ.md",

"section":"开户流程"

}

}
```

---

# 11. Milvus 数据结构设计

统一 Schema：

```json
{
"id":"uuid",

"vector":[],

"content":"文本内容",

"metadata":{

"document_name":"xxx.pdf",

"department":"销售部",

"doc_type":"policy",

"chunk_type":"node",

"page":12,

"section":"第三章",

"article":"第十二条"

}

}
```

---

# 12. Retrieval 检索架构

采用 Multi-Route Retrieval。

```text
                 Query

                   |

            Query Rewrite

                   |

------------------------------------------------

 |                 |                |

Vector Search   Metadata Filter   BM25 Search

 |                 |                |

Semantic        Department       Keyword


------------------------------------------------

                   |

              Result Merge

                   |

               Reranker

                   |

             Context Builder
```

---

# 13. Reranker 排序

流程：

第一阶段：

Recall

Milvus：

Top 50

第二阶段：

Reranker

模型：

* BGE-Reranker-large
* BGE-Reranker-v2-m3

输出：

Top 5 高质量 Context。

---

# 14. Tool Agent 设计

## 14.1 设计目标

Tool Agent 不直接暴露大量 API。

采用：

```
Skill + MCP
```

实现：

* 工具动态发现
* 降低 Token 消耗
* 企业系统统一接入

---

# 15. MCP 架构

企业系统通过 MCP Server 暴露。

架构：

```text
Tool Agent

    |

MCP Client

    |

-------------------------

CRM MCP Server

Database MCP Server

Report MCP Server

ERP MCP Server

-------------------------
```

---

# 16. Skill 机制

## 16.1 为什么需要 Skill

传统方式：

所有 Tool 注册到 Agent。

问题：

* Tool Schema 过多
* Context 增大
* Token 消耗高
* Agent 决策变慢

Skill 模式：

Agent 只加载能力描述。

例如：

```text
Available Skills:

1. CRM Customer Analysis

2. Sales Data Analysis

3. Finance Query

4. Report Generation
```

---

# 17. Skill 示例

## CRM Skill

```yaml
skill_name:
 customer_analysis


description:
 查询客户信息、订单历史、客户价值


tools:

- get_customer_profile

- get_purchase_history

- calculate_customer_score
```

执行时：

加载对应 MCP Tool。

---

# 18. MCP Tool 示例

## CRM MCP Server

提供：

```
customer.query

customer.history

customer.score
```

## Database MCP Server

提供：

```
sql.execute

schema.list

table.describe
```

## Knowledge MCP Server

提供：

```
knowledge.search

knowledge.retrieve

knowledge.citation
```

---

# 19. Tool Agent 执行流程

用户：

> 分析华东地区客户流失原因

流程：

```text
Supervisor Agent

↓

生成任务计划

↓

Tool Agent

↓

Skill Router

↓

加载:

CRM Skill

SQL Skill

Web Skill

↓

调用 MCP Server

↓

返回结果
```

---

# 20. 数据来源追踪

所有 Agent 输出必须保留 Source。

统一结构：

```json
{
"source":{

"system":"CRM",

"api":"customer.query",

"time":"2026-08-21"

}
}
```

知识库引用：

包含：

* 文件名称
* 页码
* 章节
* 条款

保证：

企业回答可审计。

---

# 21. Backend 架构

技术：

* FastAPI

目录：

```text
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

│   ├── retriever.py


├── tools

│   ├── mcp_client.py

│   ├── sql_tool.py

│   └── api_tool.py

```

---

# 22. 技术栈

## Agent

* DeepAgents
* LangGraph

## RAG

* LangGraph

## Vector Database

* Milvus

## LLM

* Qwen2.5
* Qwen3
* DeepSeek

## Embedding

* BGE-M3

## Backend

* FastAPI

## Database

* PostgreSQL

## Cache

* Redis

---
