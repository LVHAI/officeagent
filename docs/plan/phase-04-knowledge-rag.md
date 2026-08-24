# Phase 4：Knowledge Agent / RAG

Knowledge Agent 使用确定性的 RAG Pipeline，不为了使用 DeepAgents 而增加不必要的 Agent Loop。

实现：

- Document Parser
- Markdown / semantic document parsing
- Parent-Child Document
- Semantic Chunking
- Embedding
- Milvus Schema
- Vector Search
- Metadata Filter
- BM25
- Result Merge
- Reranker
- Top-K Context
- Citation

流程：

```text
Query
 ↓
Query Rewrite
 ↓
Vector + BM25
 ↓
Merge
 ↓
Reranker
 ↓
Context Builder
 ↓
Citation Answer
```

Knowledge Agent 由 LangGraph 调度，不能自行绕过 Supervisor 直接被所有请求无条件调用。
