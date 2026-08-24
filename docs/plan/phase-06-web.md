# Phase 6：Web Agent

Web Agent 使用 Tavily。

职责：

- Web Search
- Result Filtering
- Evidence Extraction
- URL / Source Tracking

Web Agent 不默认使用 DeepAgents。

只有 Supervisor 判断需要外部最新信息时才调用 Web Agent。
